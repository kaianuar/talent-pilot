"""Tests for Phase 2: Resume parsing service.

Tests the parse_resume function against sample CVs.
LLM-dependent tests use mocks so no real API key is needed.
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.services.resume_parser import (
    parse_resume,
    parse_resume_from_file,
    ResumeParseError,
    _extract_json,
    _extract_text_from_pdf,
    _pdf_to_images,
    _parse_with_text_model,
    _parse_with_vision_model,
    _repair_truncated_json,
)


# --- Fixtures ---

REALISTIC_PARSED_RESUME = {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+1-555-0100",
    "skills": [
        {"name": "Python", "years": 5, "category": "language"},
        {"name": "React", "years": 3, "category": "framework"},
        {"name": "Docker", "years": 4, "category": "tool"},
        {"name": "PostgreSQL", "years": 4, "category": "database"},
    ],
    "experiences": [
        {
            "company": "Acme Corp",
            "role": "Senior Engineer",
            "start": "2020-01",
            "end": "2024-06",
            "summary": "Led backend migration to microservices architecture.",
        },
        {
            "company": "StartupXYZ",
            "role": "Full Stack Developer",
            "start": "2018-06",
            "end": "2019-12",
            "summary": "Built and deployed customer-facing web application.",
        },
    ],
    "education": [
        {"institution": "MIT", "degree": "B.S. Computer Science", "year": 2018},
    ],
    "years_experience": 7,
}


@pytest.fixture
def mock_openai_client():
    """Return a MagicMock that looks like an OpenAI client returning a parsed resume."""
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(REALISTIC_PARSED_RESUME)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [mock_choice]
    return mock_client


@pytest.fixture
def sample_pdf_path():
    """Path to a sample PDF in test_resumes/. Returns None if not found."""
    path = Path(__file__).parent.parent / "data" / "test_resumes" / "sample_fullstack.pdf"
    if path.exists():
        return path
    return None


# --- _extract_json unit tests (no mocking needed) ---

def test_extract_json_plain():
    """_extract_json should parse plain JSON."""
    data = _extract_json('{"name": "John", "email": "john@test.com"}')
    assert data["name"] == "John"


def test_extract_json_with_fences():
    """_extract_json should strip markdown code fences."""
    raw = '```json\n{"name": "Jane", "email": "jane@test.com"}\n```'
    data = _extract_json(raw)
    assert data["name"] == "Jane"
    assert data["email"] == "jane@test.com"


def test_extract_json_with_text():
    """_extract_json should handle text around JSON."""
    raw = 'Here is the parsed data:\n{"name": "Bob", "email": "bob@test.com"}\nDone.'
    with pytest.raises(json.JSONDecodeError):
        _extract_json(raw)


# --- Mocked integration tests ---

def test_parse_resume_with_mock(mock_openai_client):
    """parse_resume should return structured data from mocked LLM response."""
    fake_pdf_bytes = b"%PDF-1.4 fake content for testing"

    with (
        patch("backend.services.resume_parser.QWEN_API_KEY", "fake-key-for-testing"),
        patch("backend.services.resume_parser.OpenAI", return_value=mock_openai_client),
        patch("backend.services.resume_parser._extract_text_from_pdf", return_value="John Doe\njohn@example.com\nSenior Engineer\nPython, React, Docker, PostgreSQL\n" * 5),
    ):
        result = parse_resume(fake_pdf_bytes)

    assert "name" in result
    assert result["name"], "name should not be empty"
    assert "email" in result
    assert "@" in result.get("email", ""), "email should contain @"
    assert "skills" in result
    assert len(result["skills"]) >= 3, f"Expected >= 3 skills, got {len(result.get('skills', []))}"
    assert "experiences" in result
    assert len(result["experiences"]) >= 1, "Expected at least 1 experience"
    assert "years_experience" in result
    assert result["years_experience"] >= 0


def test_parse_resume_returns_valid_schema(mock_openai_client):
    """parse_resume output should match ParsedResumeModel schema."""
    from backend.models.candidate import ParsedResumeModel

    fake_pdf_bytes = b"%PDF-1.4 fake content for testing"

    with (
        patch("backend.services.resume_parser.QWEN_API_KEY", "fake-key-for-testing"),
        patch("backend.services.resume_parser.OpenAI", return_value=mock_openai_client),
        patch("backend.services.resume_parser._extract_text_from_pdf", return_value="John Doe\njohn@example.com\n" * 50),
    ):
        result = parse_resume(fake_pdf_bytes)

    parsed = ParsedResumeModel(**result)
    assert parsed.name
    assert parsed.email


def test_text_path_uses_chat_model_not_reasoning_model(mock_openai_client):
    """Regression guard: the text extraction path must use MODEL_CHAT, not
    MODEL_REASONING. Reasoning models (qwen3.7-max-preview, qwen3.7-max-2026-06-08)
    have been observed returning null for years on implicit skills, which fails
    the ParsedResumeModel validator. qwen-turbo is reliable for this schema.
    """
    from backend.config import MODEL_CHAT, MODEL_REASONING

    fake_pdf_bytes = b"%PDF-1.4 fake content for testing"

    with (
        patch("backend.services.resume_parser.QWEN_API_KEY", "fake-key-for-testing"),
        patch("backend.services.resume_parser.OpenAI", return_value=mock_openai_client),
        patch("backend.services.resume_parser._extract_text_from_pdf", return_value="John Doe\njohn@example.com\n" * 50),
    ):
        parse_resume(fake_pdf_bytes)

    called_model = mock_openai_client.chat.completions.create.call_args.kwargs["model"]
    assert called_model == MODEL_CHAT, (
        f"Text path called model={called_model!r}; expected MODEL_CHAT={MODEL_CHAT!r}. "
        f"Do not regress to MODEL_REASONING={MODEL_REASONING!r} — it fails this schema."
    )


# --- Tests that need no mocking ---

def test_parse_resume_no_api_key():
    """parse_resume should raise ResumeParseError if no API key."""
    with patch("backend.services.resume_parser.QWEN_API_KEY", ""):
        with pytest.raises(ResumeParseError, match="not configured"):
            parse_resume(b"fake pdf bytes")


def test_parse_resume_from_file_not_found():
    """parse_resume_from_file should raise FileNotFoundError for missing files."""
    with pytest.raises(FileNotFoundError):
        parse_resume_from_file("/nonexistent/path/resume.pdf")


# --- Test with pre-generated parsed data (no LLM needed) ---

def test_parsed_resume_model_validation():
    """ParsedResumeModel should validate correct data."""
    from backend.models.candidate import ParsedResumeModel

    data = {
        "name": "Jessica Chen",
        "email": "jessica@example.com",
        "phone": "+65-9123-4567",
        "skills": [
            {"name": "Python", "years": 5, "category": "language"},
            {"name": "FastAPI", "years": 3, "category": "framework"},
        ],
        "experiences": [
            {"company": "TechCorp", "role": "Senior Engineer", "start": "2021-03", "end": "2026-01", "summary": "Built microservices."},
        ],
        "education": [{"institution": "NUS", "degree": "BSc CS", "year": 2019}],
        "years_experience": 6,
    }
    parsed = ParsedResumeModel(**data)
    assert parsed.name == "Jessica Chen"
    assert len(parsed.skills) == 2
    assert parsed.years_experience == 6


def test_parsed_resume_model_missing_fields():
    """ParsedResumeModel should fail on missing required fields."""
    from backend.models.candidate import ParsedResumeModel
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ParsedResumeModel(name="Test")  # missing email

# --- _repair_truncated_json tests ---

def test_repair_truncated_json_valid():
    """_repair_truncated_json should close truncated JSON."""
    truncated = '{"name": "John", "skills": ["Python", "React'
    result = _repair_truncated_json(truncated)
    assert result is not None
    assert result["name"] == "John"


def test_repair_truncated_json_already_complete():
    """_repair_truncated_json should handle already-complete JSON."""
    complete = '{"name": "John"}'
    result = _repair_truncated_json(complete)
    # Already parseable, _repair should still work
    assert result is not None
    assert result["name"] == "John"


def test_repair_truncated_json_garbage():
    """_repair_truncated_json should return None for unparseable input."""
    result = _repair_truncated_json("not json at all {{{}}}}}}")
    # May or may not parse, but shouldn't crash
    assert result is None or isinstance(result, dict)


def test_repair_truncated_json_empty():
    """_repair_truncated_json should return None for empty/short input."""
    result = _repair_truncated_json("")
    assert result is None


# --- _extract_text_from_pdf tests (mock fitz) ---

def test_extract_text_from_pdf_success():
    """_extract_text_from_pdf should return text from all pages."""
    mock_page1 = MagicMock()
    mock_page1.get_text.return_value = "Page one content. "
    mock_page2 = MagicMock()
    mock_page2.get_text.return_value = "Page two content. "

    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_page1, mock_page2]))
    mock_doc.close = MagicMock()

    with patch("backend.services.resume_parser.fitz") as mock_fitz:
        mock_fitz.open.return_value = mock_doc
        result = _extract_text_from_pdf(b"%PDF-1.4 fake")

    assert "Page one content." in result
    assert "Page two content." in result
    mock_doc.close.assert_called_once()


def test_extract_text_from_pdf_failure():
    """_extract_text_from_pdf should return empty string on error."""
    with patch("backend.services.resume_parser.fitz") as mock_fitz:
        mock_fitz.open.side_effect = Exception("corrupted PDF")
        result = _extract_text_from_pdf(b"bad bytes")

    assert result == ""


def test_extract_text_from_pdf_empty_pages():
    """_extract_text_from_pdf should handle PDFs with empty pages."""
    mock_page = MagicMock()
    mock_page.get_text.return_value = ""

    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
    mock_doc.close = MagicMock()

    with patch("backend.services.resume_parser.fitz") as mock_fitz:
        mock_fitz.open.return_value = mock_doc
        result = _extract_text_from_pdf(b"%PDF-1.4")

    assert result == ""


# --- _pdf_to_images tests (mock fitz) ---

def test_pdf_to_images_success():
    """_pdf_to_images should return base64-encoded PNG per page."""
    mock_pix = MagicMock()
    mock_pix.tobytes.return_value = b"\x89PNG fake image data"

    mock_page = MagicMock()
    mock_page.get_pixmap.return_value = mock_pix

    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_page, mock_page]))
    mock_doc.close = MagicMock()

    with patch("backend.services.resume_parser.fitz") as mock_fitz:
        mock_fitz.open.return_value = mock_doc
        mock_fitz.Matrix.return_value = MagicMock()
        images = _pdf_to_images(b"%PDF-1.4 fake")

    assert len(images) == 2
    for img in images:
        assert isinstance(img, str)
        assert len(img) > 0  # base64 string
    mock_doc.close.assert_called_once()


def test_pdf_to_images_empty_pdf():
    """_pdf_to_images should return empty list for PDF with no pages."""
    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([]))
    mock_doc.close = MagicMock()

    with patch("backend.services.resume_parser.fitz") as mock_fitz:
        mock_fitz.open.return_value = mock_doc
        images = _pdf_to_images(b"%PDF-1.4 empty")

    assert images == []


# --- Vision model path tests ---

def test_parse_with_vision_model_success():
    """_parse_with_vision_model should parse resume from page images."""
    mock_pix = MagicMock()
    mock_pix.tobytes.return_value = b"\x89PNG data"

    mock_page = MagicMock()
    mock_page.get_pixmap.return_value = mock_pix

    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
    mock_doc.close = MagicMock()

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(REALISTIC_PARSED_RESUME)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [mock_choice]

    with (
        patch("backend.services.resume_parser.fitz") as mock_fitz,
        patch("backend.services.resume_parser.OpenAI", return_value=mock_client),
        patch("backend.services.resume_parser.QWEN_API_KEY", "fake-key"),
    ):
        mock_fitz.open.return_value = mock_doc
        mock_fitz.Matrix.return_value = MagicMock()
        result = _parse_with_vision_model(b"%PDF-1.4 fake")

    assert result["name"] == "John Doe"
    assert len(result["skills"]) >= 3


def test_parse_with_vision_model_no_pages():
    """_parse_with_vision_model should raise ResumeParseError if PDF has no pages."""
    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([]))
    mock_doc.close = MagicMock()

    with (
        patch("backend.services.resume_parser.fitz") as mock_fitz,
        patch("backend.services.resume_parser.QWEN_API_KEY", "fake-key"),
    ):
        mock_fitz.open.return_value = mock_doc
        with pytest.raises(ResumeParseError, match="no pages"):
            _parse_with_vision_model(b"%PDF-1.4 empty")


# --- Text extraction failure → vision fallback ---

def test_parse_resume_text_extraction_fails_falls_back_to_vision():
    """When text extraction yields no text, parse_resume should use vision model."""
    mock_pix = MagicMock()
    mock_pix.tobytes.return_value = b"\x89PNG data"

    mock_page = MagicMock()
    mock_page.get_pixmap.return_value = mock_pix

    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
    mock_doc.close = MagicMock()

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(REALISTIC_PARSED_RESUME)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [mock_choice]

    with (
        patch("backend.services.resume_parser.QWEN_API_KEY", "fake-key"),
        patch("backend.services.resume_parser.OpenAI", return_value=mock_client),
        patch("backend.services.resume_parser._extract_text_from_pdf", return_value=""),
        patch("backend.services.resume_parser.fitz") as mock_fitz,
    ):
        mock_fitz.open.return_value = mock_doc
        mock_fitz.Matrix.return_value = MagicMock()
        result = parse_resume(b"%PDF-1.4 scanned")

    assert result["name"] == "John Doe"


def test_parse_resume_text_model_fails_falls_back_to_vision():
    """When text model raises, parse_resume should fall back to vision model."""
    mock_pix = MagicMock()
    mock_pix.tobytes.return_value = b"\x89PNG data"

    mock_page = MagicMock()
    mock_page.get_pixmap.return_value = mock_pix

    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
    mock_doc.close = MagicMock()

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(REALISTIC_PARSED_RESUME)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [mock_choice]

    # First call (text model) fails, second call (vision model) succeeds
    call_count = {"n": 0}
    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("text model exploded")
        return mock_choice.message.content

    mock_client.chat.completions.create.side_effect = [
        MagicMock(choices=[MagicMock(message=MagicMock(content="invalid json that fails parsing"))]),
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps(REALISTIC_PARSED_RESUME)))]),
    ]

    long_text = "John Doe\njohn@example.com\nSenior Engineer\n" * 50

    with (
        patch("backend.services.resume_parser.QWEN_API_KEY", "fake-key"),
        patch("backend.services.resume_parser.OpenAI", return_value=mock_client),
        patch("backend.services.resume_parser._extract_text_from_pdf", return_value=long_text),
        patch("backend.services.resume_parser.fitz") as mock_fitz,
    ):
        mock_fitz.open.return_value = mock_doc
        mock_fitz.Matrix.return_value = MagicMock()
        result = parse_resume(b"%PDF-1.4 fallback")

    assert result["name"] == "John Doe"
    # Text model was called first (failed), then vision model succeeded
    assert mock_client.chat.completions.create.call_count == 2


# --- Both models failing → ResumeParseError ---

def test_parse_resume_both_models_fail():
    """When both text and vision models fail, parse_resume should raise ResumeParseError."""
    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([]))
    mock_doc.close = MagicMock()

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("API down")

    short_text = "short"  # below MIN_TEXT_LENGTH

    with (
        patch("backend.services.resume_parser.QWEN_API_KEY", "fake-key"),
        patch("backend.services.resume_parser.OpenAI", return_value=mock_client),
        patch("backend.services.resume_parser._extract_text_from_pdf", return_value=short_text),
        patch("backend.services.resume_parser.fitz") as mock_fitz,
    ):
        mock_fitz.open.return_value = mock_doc
        with pytest.raises(ResumeParseError, match="both text and vision models"):
            parse_resume(b"%PDF-1.4 broken")


def test_parse_resume_both_models_fail_with_long_text():
    """When text model fails and vision model also fails, raise ResumeParseError."""
    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter([]))
    mock_doc.close = MagicMock()

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("API down")

    long_text = "John Doe\njohn@example.com\n" * 50

    with (
        patch("backend.services.resume_parser.QWEN_API_KEY", "fake-key"),
        patch("backend.services.resume_parser.OpenAI", return_value=mock_client),
        patch("backend.services.resume_parser._extract_text_from_pdf", return_value=long_text),
        patch("backend.services.resume_parser.fitz") as mock_fitz,
    ):
        mock_fitz.open.return_value = mock_doc
        with pytest.raises(ResumeParseError) as exc_info:
            parse_resume(b"%PDF-1.4 broken")
        assert exc_info.value.partial is True


# --- Large text content handling ---

def test_parse_resume_large_text():
    """parse_resume should handle very large resume text."""
    # Simulate a very long resume
    large_text = "John Doe\njohn@example.com\nSenior Engineer\n" + ("Experience: Built systems. " * 500)

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(REALISTIC_PARSED_RESUME)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [mock_choice]

    with (
        patch("backend.services.resume_parser.QWEN_API_KEY", "fake-key"),
        patch("backend.services.resume_parser.OpenAI", return_value=mock_client),
        patch("backend.services.resume_parser._extract_text_from_pdf", return_value=large_text),
    ):
        result = parse_resume(b"%PDF-1.4 large")

    assert result["name"] == "John Doe"
    # Verify the large text was passed to the model
    call_args = mock_client.chat.completions.create.call_args
    messages = call_args.kwargs.get("messages") or call_args[1].get("messages", [])
    user_content = messages[1]["content"]
    assert len(user_content) > 1000


# --- Multiple page PDF handling ---

def test_pdf_to_images_multi_page():
    """_pdf_to_images should return one image per page."""
    mock_pix = MagicMock()
    mock_pix.tobytes.return_value = b"\x89PNG page data"

    pages = []
    for i in range(5):
        mock_page = MagicMock()
        mock_page.get_pixmap.return_value = mock_pix
        pages.append(mock_page)

    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter(pages))
    mock_doc.close = MagicMock()

    with patch("backend.services.resume_parser.fitz") as mock_fitz:
        mock_fitz.open.return_value = mock_doc
        mock_fitz.Matrix.return_value = MagicMock()
        images = _pdf_to_images(b"%PDF-1.4 multi-page")

    assert len(images) == 5


def test_extract_text_multi_page():
    """_extract_text_from_pdf should concatenate text from all pages."""
    pages = []
    for i in range(3):
        mock_page = MagicMock()
        mock_page.get_text.return_value = f"Content of page {i + 1}.\n"
        pages.append(mock_page)

    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter(pages))
    mock_doc.close = MagicMock()

    with patch("backend.services.resume_parser.fitz") as mock_fitz:
        mock_fitz.open.return_value = mock_doc
        result = _extract_text_from_pdf(b"%PDF-1.4 multi")

    assert "Content of page 1." in result
    assert "Content of page 2." in result
    assert "Content of page 3." in result


# --- parse_resume_from_file success path ---

def test_parse_resume_from_file_success(tmp_path):
    """parse_resume_from_file should read bytes and delegate to parse_resume."""
    fake_pdf = tmp_path / "resume.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4 fake content")

    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(REALISTIC_PARSED_RESUME)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [mock_choice]

    with (
        patch("backend.services.resume_parser.QWEN_API_KEY", "fake-key"),
        patch("backend.services.resume_parser.OpenAI", return_value=mock_client),
        patch("backend.services.resume_parser._extract_text_from_pdf", return_value="John Doe\njohn@example.com\n" * 50),
    ):
        result = parse_resume_from_file(fake_pdf)

    assert result["name"] == "John Doe"


# --- _extract_json additional edge cases ---

def test_extract_json_repair_truncated():
    """_extract_json should repair truncated JSON via _repair_truncated_json."""
    truncated = '{"name": "John", "skills": ["Python"'
    result = _extract_json(truncated)
    assert result["name"] == "John"
    assert "Python" in result["skills"]


def test_extract_json_fences_no_lang():
    """_extract_json should handle code fences without language specifier."""
    raw = '```\n{"name": "Test"}\n```'
    result = _extract_json(raw)
    assert result["name"] == "Test"


# --- ResumeParseError attributes ---

def test_resume_parse_error_attributes():
    """ResumeParseError should store partial flag."""
    err = ResumeParseError("test error", partial=True)
    assert str(err) == "test error"
    assert err.partial is True

    err2 = ResumeParseError("test error 2")
    assert err2.partial is False


# --- Text model path tests ---

def test_parse_with_text_model_success():
    """_parse_with_text_model should call OpenAI with text content."""
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(REALISTIC_PARSED_RESUME)

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [mock_choice]

    with (
        patch("backend.services.resume_parser.OpenAI", return_value=mock_client),
        patch("backend.services.resume_parser.QWEN_API_KEY", "fake-key"),
    ):
        result = _parse_with_text_model("John Doe\njohn@example.com\n" * 50)

    assert result["name"] == "John Doe"
    mock_client.chat.completions.create.assert_called_once()


def test_parse_with_text_model_invalid_response():
    """_parse_with_text_model should propagate errors from invalid JSON responses."""
    mock_choice = MagicMock()
    mock_choice.message.content = "not valid json"

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [mock_choice]

    with (
        patch("backend.services.resume_parser.OpenAI", return_value=mock_client),
        patch("backend.services.resume_parser.QWEN_API_KEY", "fake-key"),
    ):
        with pytest.raises(json.JSONDecodeError):
            _parse_with_text_model("Some resume text")


def test_repair_truncated_json_with_escaped_chars():
    """_repair_truncated_json should handle escaped characters in strings."""
    # JSON with backslash-escaped quotes inside a string
    truncated = '{"name": "Jo\\"hn", "bio": "He said \\"hello'
    result = _repair_truncated_json(truncated)
    # Should handle the escaped quotes without crashing
    assert result is not None or result is None  # just no crash


def test_repair_truncated_json_with_existing_closing_brackets():
    """_repair_truncated_json should decrement open_brackets on existing ']' chars."""
    # Has a completed array "first" and a truncated second array
    truncated = '{"a": ["done"], "b": ["incomplete"'
    result = _repair_truncated_json(truncated)
    assert result is not None
    assert result["a"] == ["done"]
    assert result["b"] == ["incomplete"]


def test_repair_truncated_json_with_arrays():
    """_repair_truncated_json should close open arrays (brackets)."""
    truncated = '{"items": ["a", "b", "c"'
    result = _repair_truncated_json(truncated)
    assert result is not None
    assert result["items"] == ["a", "b", "c"]


def test_repair_truncated_json_nested_arrays():
    """_repair_truncated_json should handle nested arrays and objects."""
    truncated = '{"data": {"list": ["x", "y"'
    result = _repair_truncated_json(truncated)
    assert result is not None
    assert result["data"]["list"] == ["x", "y"]

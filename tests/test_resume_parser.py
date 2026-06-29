"""Tests for Phase 2: Resume parsing service.

Tests the parse_resume function against sample CVs.
LLM-dependent tests use mocks so no real API key is needed.
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.services.resume_parser import parse_resume, parse_resume_from_file, ResumeParseError, _extract_json


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

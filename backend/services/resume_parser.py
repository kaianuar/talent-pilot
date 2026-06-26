"""CV/resume parsing — hybrid approach.

Strategy:
1. Try text extraction from PDF (fast, lossless for text-based PDFs)
2. If text extraction yields enough content, use qwen3-max (text model) to parse it
3. If text extraction fails (scanned PDF, image-only), fall back to vision model with image conversion
"""

import base64
import io
import json
import logging
import re
from pathlib import Path

import fitz  # PyMuPDF
from openai import OpenAI

from backend.config import QWEN_API_KEY, QWEN_BASE_URL, MODEL_VISION, MODEL_REASONING
from backend.models.candidate import ParsedResumeModel

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a resume/CV parser. Extract the following from the document:
- name: full name
- email: email address
- phone: phone number (international format if possible)
- skills: array of {name, years, category} where category is one of: language, framework, tool, database, cloud, platform, skill. Limit to the 15 most relevant skills.
- experiences: array of {company, role, start (YYYY-MM), end (YYYY-MM or null if current), summary (1 sentence)}. Limit to the 5 most recent.
- education: array of {institution, degree, year}
- years_experience: total professional years as integer

Infer implicit skills from experience descriptions (e.g. "built REST APIs" implies "REST" and "API Design").
Be concise — return only the most relevant items, not exhaustive lists.
Return ONLY a valid JSON object, no markdown fences, no commentary."""

# Minimum characters to consider text extraction successful
MIN_TEXT_LENGTH = 100


class ResumeParseError(Exception):
    """Raised when resume parsing fails after retries."""
    def __init__(self, message: str, partial: bool = False):
        super().__init__(message)
        self.partial = partial


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, stripping markdown fences if present.
    Attempts repair if JSON is truncated (missing closing braces/brackets).
    """
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)

    # Try parsing as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt repair: find the last complete key-value pair and close the structure
    repaired = _repair_truncated_json(text)
    if repaired:
        return repaired

    raise json.JSONDecodeError("Could not parse JSON", text, 0)


def _repair_truncated_json(text: str) -> dict | None:
    """Attempt to repair a truncated JSON response by closing open braces/brackets."""
    # Strategy: truncate at the last complete value (ends with } or ] or ",)
    # then close all open structures

    # Find the last position where we have a complete value
    # Look for the last occurrence of a closing quote followed by optional comma
    last_good = -1
    for i in range(len(text) - 1, -1, -1):
        if text[i] in ('}', ']'):
            last_good = i + 1
            break
        if text[i] == '"' and i > 0:
            # Check if this is a closing quote (not preceded by \)
            if text[i-1] != '\\':
                # Check what follows — should be , or : or } or ]
                rest = text[i+1:].strip()
                if rest == '' or rest.startswith(',') or rest.startswith(':') or rest.startswith('}') or rest.startswith(']'):
                    last_good = i + 1
                    break

    if last_good <= 0:
        return None

    truncated = text[:last_good]

    # Count open braces and brackets
    open_braces = 0
    open_brackets = 0
    in_string = False
    escape_next = False

    for ch in truncated:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            open_braces += 1
        elif ch == '}':
            open_braces -= 1
        elif ch == '[':
            open_brackets += 1
        elif ch == ']':
            open_brackets -= 1

    # Remove trailing comma if present
    repaired = truncated.rstrip().rstrip(',')

    # Close open arrays and objects
    repaired += ']' * open_brackets
    repaired += '}' * open_braces

    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF using PyMuPDF. Returns empty string if extraction fails."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text.strip()
    except Exception as e:
        logger.warning("Text extraction failed: %s", e)
        return ""


def _pdf_to_images(pdf_bytes: bytes) -> list[str]:
    """Convert PDF bytes to a list of base64-encoded PNG images (one per page)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []
    for page in doc:
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        png_bytes = pix.tobytes(output="png")
        b64 = base64.b64encode(png_bytes).decode("utf-8")
        images.append(b64)
    doc.close()
    return images


def _parse_with_text_model(text_content: str) -> dict:
    """Parse resume using the text-based reasoning model (qwen3-max)."""
    client = OpenAI(base_url=QWEN_BASE_URL, api_key=QWEN_API_KEY)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Parse this resume/CV text and return the structured JSON:\n\n{text_content}"},
    ]

    response = client.chat.completions.create(
        model=MODEL_REASONING,
        messages=messages,
        temperature=0.1,
        max_tokens=4000,
    )
    raw = response.choices[0].message.content
    data = _extract_json(raw)
    parsed = ParsedResumeModel(**data)
    return parsed.model_dump()


def _parse_with_vision_model(pdf_bytes: bytes) -> dict:
    """Parse resume using the vision model (Qwen3-VL-Plus) with page images."""
    page_images = _pdf_to_images(pdf_bytes)
    if not page_images:
        raise ResumeParseError("PDF has no pages.")

    content = []
    for img_b64 in page_images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{img_b64}"},
        })
    content.append({"type": "text", "text": "Parse this resume/CV and return the structured JSON."})

    client = OpenAI(base_url=QWEN_BASE_URL, api_key=QWEN_API_KEY)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]

    response = client.chat.completions.create(
        model=MODEL_VISION,
        messages=messages,
        temperature=0.1,
        max_tokens=4000,
    )
    raw = response.choices[0].message.content
    data = _extract_json(raw)
    parsed = ParsedResumeModel(**data)
    return parsed.model_dump()


def parse_resume(pdf_bytes: bytes) -> dict:
    """Parse a resume PDF into structured data.

    Hybrid strategy:
    1. Extract text from PDF
    2. If enough text → use text model (faster, cheaper, lossless)
    3. If too little text (scanned/image PDF) → convert to images and use vision model

    Args:
        pdf_bytes: Raw PDF file bytes.

    Returns:
        Parsed resume dict matching ParsedResumeModel schema.

    Raises:
        ResumeParseError: If parsing fails after retries.
    """
    if not QWEN_API_KEY:
        raise ResumeParseError("QWEN_API_KEY not configured. Set it in environment or .env file.")

    # Step 1: Try text extraction
    text_content = _extract_text_from_pdf(pdf_bytes)

    if len(text_content) >= MIN_TEXT_LENGTH:
        # Text-based PDF — use the cheaper/faster text model
        logger.info("PDF has %d chars of text, using text model", len(text_content))
        try:
            return _parse_with_text_model(text_content)
        except Exception as e:
            logger.warning("Text model parse failed (%s), falling back to vision model", e)
            # Fall through to vision model
    else:
        logger.info("PDF has only %d chars of text, using vision model (likely scanned)", len(text_content))

    # Step 2: Fallback to vision model for scanned/image PDFs
    try:
        return _parse_with_vision_model(pdf_bytes)
    except Exception as e:
        raise ResumeParseError(f"Failed to parse resume with both text and vision models: {e}", partial=True)


def parse_resume_from_file(file_path: str | Path) -> dict:
    """Convenience: read a file and parse it."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return parse_resume(path.read_bytes())

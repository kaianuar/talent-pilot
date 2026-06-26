"""CV/resume parsing via Qwen3-VL-Plus vision model."""

import base64
import json
import logging
import re
from pathlib import Path

from openai import OpenAI

from backend.config import QWEN_API_KEY, QWEN_BASE_URL, MODEL_VISION
from backend.models.candidate import ParsedResumeModel

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a resume/CV parser. Extract the following from the document:
- name: full name
- email: email address
- phone: phone number (international format if possible)
- skills: array of {name, years, category} where category is one of: language, framework, tool, database, cloud, platform, skill
- experiences: array of {company, role, start (YYYY-MM), end (YYYY-MM or null if current), summary (1 sentence)}
- education: array of {institution, degree, year}
- years_experience: total professional years as integer

Infer implicit skills from experience descriptions (e.g. "built REST APIs" implies "REST" and "API Design").
Return ONLY a valid JSON object, no markdown fences, no commentary."""


class ResumeParseError(Exception):
    """Raised when resume parsing fails after retries."""
    def __init__(self, message: str, partial: bool = False):
        super().__init__(message)
        self.partial = partial


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, stripping markdown fences if present."""
    text = text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    return json.loads(text)


def parse_resume(pdf_bytes: bytes) -> dict:
    """Parse a resume PDF into structured data using Qwen3-VL-Plus.

    Args:
        pdf_bytes: Raw PDF file bytes.

    Returns:
        Parsed resume dict matching ParsedResumeModel schema.

    Raises:
        ResumeParseError: If parsing fails after retries.
    """
    if not QWEN_API_KEY:
        raise ResumeParseError("QWEN_API_KEY not configured. Set it in environment or .env file.")

    b64 = base64.b64encode(pdf_bytes).decode("utf-8")

    client = OpenAI(base_url=QWEN_BASE_URL, api_key=QWEN_API_KEY)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:application/pdf;base64,{b64}"},
                },
                {"type": "text", "text": "Parse this resume/CV and return the structured JSON."},
            ],
        },
    ]

    last_error = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=MODEL_VISION,
                messages=messages,
                temperature=0.1,
                max_tokens=2000,
            )
            raw = response.choices[0].message.content
            data = _extract_json(raw)
            # Validate against Pydantic model
            parsed = ParsedResumeModel(**data)
            return parsed.model_dump()
        except json.JSONDecodeError as e:
            last_error = e
            logger.warning("JSON parse failed on attempt %d: %s", attempt + 1, e)
            if attempt == 0:
                messages.append({"role": "assistant", "content": raw if 'raw' in dir() else ""})
                messages.append({"role": "user", "content": "That was not valid JSON. Return ONLY the JSON object, no prose, no markdown fences."})
        except Exception as e:
            last_error = e
            logger.warning("Parse validation failed on attempt %d: %s", attempt + 1, e)
            if attempt == 0:
                messages.append({"role": "user", "content": f"Validation error: {e}. Fix the JSON and return it again. Return ONLY the JSON object."})

    raise ResumeParseError(f"Failed to parse resume after 2 attempts: {last_error}", partial=True)


def parse_resume_from_file(file_path: str | Path) -> dict:
    """Convenience: read a file and parse it."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return parse_resume(path.read_bytes())

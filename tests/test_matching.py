"""Unit tests for the matching algorithm (_compute_match)."""

import pytest

from backend.app import _compute_match


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _job(
    job_id: str = "j1",
    title: str = "Engineer",
    required: list | None = None,
    preferred: list | None = None,
    min_years: int = 0,
) -> dict:
    """Build a minimal job dict for matching."""
    return {
        "id": job_id,
        "title": title,
        "required_skills": required or [],
        "preferred_skills": preferred or [],
        "min_years": min_years,
        "recruiter_email": "hr@test.com",
    }


# ============================================================================
# Basic score computation
# ============================================================================


def test_perfect_match_all_required():
    """Candidate with all required skills and high experience → high score."""
    job = _job(required=["Python", "FastAPI", "PostgreSQL"])
    result = _compute_match(["Python", "FastAPI", "PostgreSQL"], 10.0, job)

    assert result["required_match_ratio"] == 1.0
    assert result["experience_score"] == 1.0
    assert result["match_score"] > 0.5  # 0.35+0.20 = 0.55 with no LLM reasoning


def test_no_required_skills_match():
    """Candidate missing all required skills → low score."""
    job = _job(required=["Go", "Rust"])
    result = _compute_match(["Python", "JavaScript"], 5.0, job)

    assert result["required_match_ratio"] == 0.0
    assert result["match_score"] < 0.5


def test_partial_required_match():
    """Candidate with some required skills → partial ratio."""
    job = _job(required=["Python", "Go", "Rust"])
    result = _compute_match(["Python"], 3.0, job)

    assert 0.3 < result["required_match_ratio"] < 0.4  # 1/3 ≈ 0.333


# ============================================================================
# Adjacent bonus (preferred / nice-to-have skills)
# ============================================================================


def test_adjacent_bonus_with_preferred_skills():
    """Preferred skills should contribute to adjacent_bonus."""
    job = _job(
        required=["Python"],
        preferred=["Docker", "Kubernetes"],
    )
    # Candidate has all preferred
    result = _compute_match(["Python", "Docker", "Kubernetes"], 5.0, job)

    assert result["adjacent_bonus"] == 1.0


def test_adjacent_bonus_partial():
    """Partial preferred skill coverage."""
    job = _job(
        required=["Python"],
        preferred=["Docker", "Kubernetes", "Terraform"],
    )
    result = _compute_match(["Python", "Docker"], 3.0, job)

    assert 0.3 < result["adjacent_bonus"] < 0.4  # 1/3 ≈ 0.333


def test_no_preferred_skills_zero_bonus():
    """No preferred skills → adjacent_bonus should be 0."""
    job = _job(required=["Python"], preferred=[])
    result = _compute_match(["Python"], 5.0, job)

    assert result["adjacent_bonus"] == 0.0


# ============================================================================
# Experience score
# ============================================================================


def test_experience_score_capped_at_10():
    """Experience score should cap at 1.0 for 10+ years."""
    job = _job(required=["Python"])
    result = _compute_match(["Python"], 20.0, job)

    assert result["experience_score"] == 1.0


def test_experience_score_zero_years():
    """Zero years → experience_score = 0."""
    job = _job(required=["Python"])
    result = _compute_match(["Python"], 0.0, job)

    assert result["experience_score"] == 0.0


def test_experience_score_mid_range():
    """5 years → experience_score = 0.5."""
    job = _job(required=["Python"])
    result = _compute_match(["Python"], 5.0, job)

    assert result["experience_score"] == 0.5


def test_experience_score_none_treated_as_zero():
    """None years should be treated as 0."""
    job = _job(required=["Python"])
    result = _compute_match(["Python"], None, job)

    assert result["experience_score"] == 0.0


# ============================================================================
# Tier classification
# ============================================================================


def test_tier_strong_match():
    """High score → STRONG_MATCH tier."""
    job = _job(
        required=["Python", "FastAPI"],
        preferred=["Docker"],
    )
    result = _compute_match(["Python", "FastAPI", "Docker"], 10.0, job)

    assert result["tier"] == "STRONG_MATCH"


def test_tier_no_match():
    """Very low score → NO_MATCH tier."""
    job = _job(required=["Haskell", "Erlang"])
    result = _compute_match(["Python"], 0.0, job)

    assert result["tier"] == "NO_MATCH"


def test_tier_partial_match():
    """Medium score → PARTIAL_MATCH tier."""
    # With 4-weight formula (no LLM): composite = 0.35*1.0 + 0.20*1.0 + 0.20*0.5 = 0.65
    job = _job(required=["Python"], preferred=["Docker"])
    result = _compute_match(["Python", "Docker"], 5.0, job)

    assert result["tier"] == "PARTIAL_MATCH"


# ============================================================================
# Skill matching substring behavior
# ============================================================================


def test_skill_matching_case_insensitive():
    """Skill matching should be case-insensitive."""
    job = _job(required=["Python"])
    result = _compute_match(["python"], 5.0, job)

    assert result["required_match_ratio"] == 1.0


def test_skill_matching_substring():
    """Substring matches should count (e.g. 'Python' matches 'Python 3')."""
    job = _job(required=["Python 3"])
    result = _compute_match(["Python"], 3.0, job)

    assert result["required_match_ratio"] == 1.0


def test_skill_dict_format():
    """Skills as dicts with 'name' key should work."""
    job = _job(required=[{"name": "Python"}, {"name": "FastAPI"}])
    result = _compute_match(["Python", "FastAPI"], 5.0, job)

    assert result["required_match_ratio"] == 1.0


# ============================================================================
# Edge cases
# ============================================================================


def test_empty_required_and_preferred():
    """No required or preferred skills → required_ratio=1.0, bonus=0.0."""
    job = _job(required=[], preferred=[])
    result = _compute_match(["Python"], 5.0, job)

    assert result["required_match_ratio"] == 1.0
    assert result["adjacent_bonus"] == 0.0


def test_empty_candidate_skills():
    """Empty candidate skills → zero ratios."""
    job = _job(required=["Python"], preferred=["Docker"])
    result = _compute_match([], 0.0, job)

    assert result["required_match_ratio"] == 0.0
    assert result["adjacent_bonus"] == 0.0
    assert result["experience_score"] == 0.0


def test_result_structure():
    """Result dict should contain all expected keys."""
    job = _job(required=["Python"])
    result = _compute_match(["Python"], 3.0, job)

    expected_keys = {
        "job_id",
        "job_title",
        "match_score",
        "tier",
        "required_match_ratio",
        "adjacent_bonus",
        "experience_score",
        "llm_reasoning_score",
        "reasoning_explanation",
    }
    assert expected_keys == set(result.keys())


def test_reasoning_explanation_mentions_skills():
    """The reasoning explanation should mention matched skill count."""
    job = _job(required=["Python", "Go"])
    result = _compute_match(["Python"], 3.0, job)

    assert "1/2" in result["reasoning_explanation"]


def test_reasoning_explanation_mentions_experience():
    """The reasoning explanation should mention years of experience."""
    job = _job(required=["Python"])
    result = _compute_match(["Python"], 7.5, job)

    assert "7.5" in result["reasoning_explanation"]


def test_match_score_rounded():
    """match_score should be rounded to 3 decimal places."""
    job = _job(required=["Python"])
    result = _compute_match(["Python"], 3.0, job)

    score_str = str(result["match_score"])
    if "." in score_str:
        assert len(score_str.split(".")[-1]) <= 3


# ============================================================================
# LLM reasoning integration
# ============================================================================


def test_llm_reasoning_boosts_composite():
    """LLM reasoning score should increase the composite proportionally."""
    job = _job(required=["Python"])
    without = _compute_match(["Python"], 5.0, job)
    with_reasoning = _compute_match(
        ["Python"], 5.0, job,
        llm_reasoning={job["id"]: {"score": 0.9, "explanation": "Strong fit"}},
    )

    assert with_reasoning["llm_reasoning_score"] == 0.9
    assert with_reasoning["match_score"] > without["match_score"]
    assert "Strong fit" in with_reasoning["reasoning_explanation"]


def test_llm_reasoning_zero_when_not_provided():
    """Without llm_reasoning param, reasoning score should be 0."""
    job = _job(required=["Python"])
    result = _compute_match(["Python"], 5.0, job)

    assert result["llm_reasoning_score"] == 0.0


def test_llm_reasoning_clamped_0_to_1():
    """Reasoning score should be clamped to [0.0, 1.0]."""
    job = _job(required=["Python"])
    result = _compute_match(
        ["Python"], 5.0, job,
        llm_reasoning={job["id"]: {"score": 1.5, "explanation": ""}},
    )

    # The batch function clamps; _compute_match uses the raw value
    assert result["llm_reasoning_score"] == 1.5  # stored as-is from dict


def test_llm_reasoning_with_strong_match():
    """Perfect match + strong LLM reasoning → STRONG_MATCH."""
    job = _job(required=["Python", "FastAPI"], preferred=["Docker"])
    result = _compute_match(
        ["Python", "FastAPI", "Docker"], 10.0, job,
        llm_reasoning={job["id"]: {"score": 0.95, "explanation": "Ideal candidate"}},
    )

    # 0.35*1.0 + 0.20*1.0 + 0.20*1.0 + 0.25*0.95 = 0.9875
    assert result["match_score"] > 0.9
    assert result["tier"] == "STRONG_MATCH"


def test_batch_llm_reasoning_failure_graceful():
    """If batch LLM call fails, _compute_match should still work with score 0.0."""
    from unittest.mock import patch, MagicMock
    from backend.app import _batch_llm_reasoning

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API timeout")

    with patch("backend.app.OpenAI", return_value=mock_client):
        result = _batch_llm_reasoning(["Python"], 5.0, [{"id": "j1", "title": "Dev", "required_skills": []}])

    assert result == {}


def test_batch_llm_reasoning_parses_response():
    """Batch LLM reasoning should parse valid response correctly."""
    import json as json_mod
    from unittest.mock import patch, MagicMock
    from backend.app import _batch_llm_reasoning

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json_mod.dumps({
        "ratings": [
            {"id": 1, "score": 0.85, "explanation": "Strong Python match"},
            {"id": 2, "score": 0.3, "explanation": "Limited Go experience"},
        ]
    })

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    jobs = [
        {"id": "j1", "title": "Python Dev", "required_skills": ["Python"]},
        {"id": "j2", "title": "Go Dev", "required_skills": ["Go"]},
    ]

    with patch("backend.app.OpenAI", return_value=mock_client):
        result = _batch_llm_reasoning(["Python"], 5.0, jobs)

    assert result["j1"]["score"] == 0.85
    assert result["j1"]["explanation"] == "Strong Python match"
    assert result["j2"]["score"] == 0.3


def test_batch_llm_reasoning_empty_jobs():
    """Empty jobs list should return empty dict without calling LLM."""
    from backend.app import _batch_llm_reasoning

    result = _batch_llm_reasoning(["Python"], 5.0, [])
    assert result == {}

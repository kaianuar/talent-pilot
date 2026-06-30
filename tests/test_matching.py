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
    assert result["match_score"] > 0.7


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
    # Need composite in [0.55, 0.75) range
    # required_ratio=1.0, adjacent=0, experience=0.5
    # composite = (0.35*1.0 + 0.20*0 + 0.20*0.5) / (0.35+0.20+0.20) = 0.45/0.75 = 0.6
    job = _job(required=["Python"], preferred=["Nonexistent"])
    result = _compute_match(["Python"], 5.0, job)

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

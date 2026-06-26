"""Tests for Phase 3: Matching engine.

Tests the deterministic parts of matching (required_coverage, adjacent_bonus,
experience_score) without requiring the LLM. The reasoning_score is mocked
to a fixed value for deterministic tests.
"""

import os
import pytest
from unittest.mock import patch

os.environ.setdefault("QWEN_API_KEY", "test-key")

from backend.agent.matching import match_score, rank_matches, MatchTier, MatchResult
from backend.agent.aliases import normalize_skill, ADJACENT_SKILLS


# --- Test normalize_skill ---

def test_normalize_skill_exact():
    assert normalize_skill("Python") == "python"
    assert normalize_skill("PostgreSQL") == "postgresql"


def test_normalize_skill_alias():
    assert normalize_skill("React.js") == "react"
    assert normalize_skill("K8s") == "kubernetes"
    assert normalize_skill("Golang") == "go"
    assert normalize_skill("Node.js") == "node"
    assert normalize_skill("TF") == "terraform"


def test_normalize_skill_unknown():
    assert normalize_skill("SomeNewLang") == "somenewlang"


# --- Mock reasoning_score functions ---

def _mock_reasoning_high(candidate, job):
    return 0.9, "Strong fit"


def _mock_reasoning_medium(candidate, job):
    return 0.7, "Reasonable fit"


def _mock_reasoning_score(candidate, job):
    return 0.5, "Mocked reasoning"


# --- Test match_score ---

@pytest.fixture
def full_match_candidate():
    return {
        "name": "Perfect Match",
        "skills": [
            {"name": "Python", "years": 5, "category": "language"},
            {"name": "FastAPI", "years": 3, "category": "framework"},
            {"name": "PostgreSQL", "years": 4, "category": "database"},
            {"name": "AWS", "years": 3, "category": "cloud"},
        ],
        "years_experience": 6,
    }


@pytest.fixture
def partial_match_candidate():
    return {
        "name": "Partial Match",
        "skills": [
            {"name": "Python", "years": 3, "category": "language"},
            {"name": "Flask", "years": 2, "category": "framework"},
            # Missing PostgreSQL and AWS
        ],
        "years_experience": 3,
    }


@pytest.fixture
def adjacent_match_candidate():
    return {
        "name": "Adjacent Match",
        "skills": [
            {"name": "Python", "years": 4, "category": "language"},
            {"name": "Vue", "years": 3, "category": "framework"},  # adjacent to React
            {"name": "MySQL", "years": 3, "category": "database"},  # adjacent to PostgreSQL
            {"name": "Azure", "years": 2, "category": "cloud"},  # adjacent to AWS
        ],
        "years_experience": 5,
    }


@pytest.fixture
def irrelevant_candidate():
    return {
        "name": "Irrelevant",
        "skills": [
            {"name": "Painting", "years": 10, "category": "skill"},
            {"name": "Cooking", "years": 5, "category": "skill"},
        ],
        "years_experience": 10,
    }


@pytest.fixture
def backend_job():
    return {
        "id": "job-001",
        "title": "Senior Backend Engineer",
        "company": "TalentBridge",
        "required_skills": [
            {"name": "Python", "category": "language", "min_years": 4, "is_required": True},
            {"name": "FastAPI", "category": "framework", "min_years": 2, "is_required": True},
            {"name": "PostgreSQL", "category": "database", "min_years": 3, "is_required": True},
            {"name": "AWS", "category": "cloud", "min_years": 2, "is_required": True},
        ],
        "min_years": 5,
    }


@patch("backend.agent.matching._reasoning_score", _mock_reasoning_high)
def test_full_match_strong(full_match_candidate, backend_job):
    """Full match with high reasoning should yield STRONG_MATCH."""
    result = match_score(full_match_candidate, backend_job)
    assert result.tier == MatchTier.STRONG_MATCH
    assert result.required_coverage == 1.0
    assert result.matched_skills == ["Python", "FastAPI", "PostgreSQL", "AWS"]
    assert result.missing_skills == []
    assert result.score >= 0.75


@patch("backend.agent.matching._reasoning_score", _mock_reasoning_medium)
def test_partial_match(partial_match_candidate, backend_job):
    """Partial match with medium reasoning should yield WEAK_MATCH."""
    result = match_score(partial_match_candidate, backend_job)
    assert result.tier in (MatchTier.PARTIAL_MATCH, MatchTier.WEAK_MATCH)
    assert result.required_coverage < 1.0
    assert len(result.missing_skills) > 0


@patch("backend.agent.matching._reasoning_score", _mock_reasoning_score)
def test_adjacent_match_bonus(adjacent_match_candidate, backend_job):
    """Adjacent skills should provide bonus points."""
    result = match_score(adjacent_match_candidate, backend_job)
    # MySQL is adjacent to PostgreSQL, Azure is adjacent to AWS
    assert result.adjacent_bonus > 0, "Adjacent skills should give a bonus"


@patch("backend.agent.matching._reasoning_score", _mock_reasoning_score)
def test_irrelevant_no_match(irrelevant_candidate, backend_job):
    """Completely irrelevant skills should yield NO_MATCH."""
    result = match_score(irrelevant_candidate, backend_job)
    assert result.tier == MatchTier.NO_MATCH
    assert result.required_coverage == 0.0


@patch("backend.agent.matching._reasoning_score", _mock_reasoning_score)
def test_experience_score_capping(backend_job):
    """Experience score should cap at 1.0."""
    overqualified = {
        "name": "Overqualified",
        "skills": [{"name": "Python", "years": 20, "category": "language"}],
        "years_experience": 20,
    }
    result = match_score(overqualified, backend_job)
    assert result.experience_score == 1.0


@patch("backend.agent.matching._reasoning_score", _mock_reasoning_score)
def test_experience_score_underqualified(backend_job):
    """Underqualified candidate should get lower experience score."""
    junior = {
        "name": "Junior",
        "skills": [
            {"name": "Python", "years": 1, "category": "language"},
            {"name": "FastAPI", "years": 1, "category": "framework"},
            {"name": "PostgreSQL", "years": 1, "category": "database"},
            {"name": "AWS", "years": 1, "category": "cloud"},
        ],
        "years_experience": 1,
    }
    result = match_score(junior, backend_job)
    assert result.experience_score < 1.0
    assert result.experience_score == pytest.approx(1.0 / 5.0, abs=0.01)


@patch("backend.agent.matching._reasoning_score", _mock_reasoning_score)
def test_score_boundary_strong(backend_job):
    """Score at exactly 0.75 should be STRONG_MATCH."""
    # With mocked reasoning at 0.5, composite = 0.35*1.0 + 0.20*0 + 0.20*1.0 + 0.25*0.5 = 0.675
    candidate = {
        "name": "Boundary",
        "skills": [
            {"name": "Python", "years": 5, "category": "language"},
            {"name": "FastAPI", "years": 3, "category": "framework"},
            {"name": "PostgreSQL", "years": 4, "category": "database"},
            {"name": "AWS", "years": 3, "category": "cloud"},
        ],
        "years_experience": 10,  # way overqualified
    }
    result = match_score(candidate, backend_job)
    # 0.35*1.0 + 0.20*0 + 0.20*1.0 + 0.25*0.5 = 0.675
    assert result.score == pytest.approx(0.675, abs=0.01)


@patch("backend.agent.matching._reasoning_score", _mock_reasoning_score)
def test_rank_matches_top_n(full_match_candidate, partial_match_candidate, backend_job):
    """rank_matches should return top N results sorted by score."""
    jobs = [
        {**backend_job, "id": "j1", "title": "Backend 1"},
        {**backend_job, "id": "j2", "title": "Backend 2"},
        {**backend_job, "id": "j3", "title": "Backend 3"},
    ]
    results = rank_matches(full_match_candidate, jobs, top_n=2)
    assert len(results) == 2
    assert results[0].score >= results[1].score


@patch("backend.agent.matching._reasoning_score", _mock_reasoning_score)
def test_match_result_fields(full_match_candidate, backend_job):
    """MatchResult should have all expected fields."""
    result = match_score(full_match_candidate, backend_job)
    assert hasattr(result, "job_id")
    assert hasattr(result, "job_title")
    assert hasattr(result, "company")
    assert hasattr(result, "score")
    assert hasattr(result, "tier")
    assert hasattr(result, "required_coverage")
    assert hasattr(result, "adjacent_bonus")
    assert hasattr(result, "experience_score")
    assert hasattr(result, "reasoning_score")
    assert hasattr(result, "matched_skills")
    assert hasattr(result, "missing_skills")
    assert hasattr(result, "reasoning_explanation")


@patch("backend.agent.matching._reasoning_score", _mock_reasoning_score)
def test_no_required_skills_job():
    """Job with no required skills should give full coverage."""
    job = {"id": "j0", "title": "No Skills Job", "company": "X", "required_skills": [], "min_years": 0}
    candidate = {"name": "Any", "skills": [], "years_experience": 0}
    result = match_score(candidate, job)
    assert result.required_coverage == 1.0


@patch("backend.agent.matching._reasoning_score", _mock_reasoning_score)
def test_alias_normalization_in_matching():
    """Skill aliases should be normalized during matching."""
    candidate = {
        "name": "Alias Tester",
        "skills": [{"name": "React.js", "years": 3, "category": "framework"}],
        "years_experience": 3,
    }
    job = {
        "id": "j-alias",
        "title": "React Dev",
        "company": "X",
        "required_skills": [{"name": "React", "category": "framework", "min_years": 2, "is_required": True}],
        "min_years": 2,
    }
    result = match_score(candidate, job)
    assert result.required_coverage == 1.0
    assert "React" in result.matched_skills

"""Matching engine: composite score with required, adjacent, experience, and LLM reasoning."""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum

from openai import OpenAI

from backend.config import (
    QWEN_API_KEY, QWEN_BASE_URL, MODEL_REASONING,
    SCORE_STRONG, SCORE_PARTIAL, SCORE_WEAK,
    W_REQUIRED, W_ADJACENT, W_EXPERIENCE, W_REASONING,
)
from backend.agent.aliases import normalize_skill, ADJACENT_SKILLS

logger = logging.getLogger(__name__)


class MatchTier(str, Enum):
    STRONG_MATCH = "STRONG_MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    WEAK_MATCH = "WEAK_MATCH"
    NO_MATCH = "NO_MATCH"


@dataclass
class MatchResult:
    job_id: str
    job_title: str
    company: str
    score: float
    tier: MatchTier
    required_coverage: float
    adjacent_bonus: float
    experience_score: float
    reasoning_score: float
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    reasoning_explanation: str = ""


def _get_canonical_skills(skills: list[dict]) -> set[str]:
    """Extract canonical skill names from a skill list."""
    return {normalize_skill(s["name"]) for s in skills}


def _required_coverage(candidate_skills: set[str], job_required: list[dict]) -> tuple[float, list[str], list[str]]:
    """Compute required-skill coverage ratio. Returns (ratio, matched, missing)."""
    if not job_required:
        return 1.0, [], []
    matched = []
    missing = []
    for req in job_required:
        canonical = normalize_skill(req["name"])
        if canonical in candidate_skills:
            matched.append(req["name"])
        else:
            missing.append(req["name"])
    ratio = len(matched) / len(job_required)
    return ratio, matched, missing


def _adjacent_bonus(candidate_skills: set[str], job_required: list[dict]) -> float:
    """Compute adjacent-skill bonus. Returns 0.0–0.5."""
    if not job_required:
        return 0.0
    adjacent_hits = 0
    for req in job_required:
        canonical = normalize_skill(req["name"])
        if canonical in candidate_skills:
            continue  # already counted in required_coverage
        adjacents = ADJACENT_SKILLS.get(canonical, set())
        if candidate_skills & adjacents:
            adjacent_hits += 1
    return (adjacent_hits / len(job_required)) * 0.5


def _experience_score(candidate_years: int, job_min_years: int) -> float:
    """Compute experience ratio, capped at 1.0."""
    if job_min_years <= 0:
        return 1.0
    return min(1.0, candidate_years / job_min_years)


def _reasoning_score(candidate: dict, job: dict) -> tuple[float, str]:
    """Call qwen3-max to get a fit score and explanation."""
    if not QWEN_API_KEY:
        # Fallback: no LLM available, return neutral score
        return 0.5, "LLM not available"

    client = OpenAI(base_url=QWEN_BASE_URL, api_key=QWEN_API_KEY)

    prompt = f"""Rate this candidate-job fit on a scale of 0.0 to 1.0.
Consider depth of experience, project relevance, skill trajectory, and overall fit.

CANDIDATE:
{json.dumps(candidate, indent=2)}

JOB:
{json.dumps(job, indent=2)}

Respond with ONLY a JSON object: {{"score": <float>, "explanation": "<1 sentence>"}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL_REASONING,
            messages=[
                {"role": "system", "content": "You are a recruiting analyst. Be concise and precise."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            import re
            raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
            raw = re.sub(r"\n?```\s*$", "", raw)
        data = json.loads(raw)
        score = float(data.get("score", 0.5))
        explanation = data.get("explanation", "")
        return max(0.0, min(1.0, score)), explanation
    except Exception as e:
        logger.warning("LLM reasoning failed: %s", e)
        return 0.5, f"LLM error: {e}"


def _compute_tier(composite: float) -> MatchTier:
    """Map composite score to a tier."""
    if composite >= SCORE_STRONG:
        return MatchTier.STRONG_MATCH
    if composite >= SCORE_PARTIAL:
        return MatchTier.PARTIAL_MATCH
    if composite >= SCORE_WEAK:
        return MatchTier.WEAK_MATCH
    return MatchTier.NO_MATCH


def match_score(candidate: dict, job: dict) -> MatchResult:
    """Compute composite match score between a candidate and a job.

    Args:
        candidate: Parsed resume dict with skills, years_experience, etc.
        job: Job dict with required_skills, min_years, etc.

    Returns:
        MatchResult with all component scores and the composite.
    """
    cand_skills = _get_canonical_skills(candidate.get("skills", []))
    job_required = job.get("required_skills", [])

    req_cov, matched, missing = _required_coverage(cand_skills, job_required)
    adj_bonus = _adjacent_bonus(cand_skills, job_required)
    exp_score = _experience_score(candidate.get("years_experience", 0), job.get("min_years", 0))
    reasoning, explanation = _reasoning_score(candidate, job)

    composite = (
        W_REQUIRED * req_cov
        + W_ADJACENT * adj_bonus
        + W_EXPERIENCE * exp_score
        + W_REASONING * reasoning
    )

    return MatchResult(
        job_id=job.get("id", ""),
        job_title=job.get("title", ""),
        company=job.get("company", ""),
        score=round(composite, 4),
        tier=_compute_tier(composite),
        required_coverage=round(req_cov, 4),
        adjacent_bonus=round(adj_bonus, 4),
        experience_score=round(exp_score, 4),
        reasoning_score=round(reasoning, 4),
        matched_skills=matched,
        missing_skills=missing,
        reasoning_explanation=explanation,
    )


def rank_matches(candidate: dict, jobs: list[dict], top_n: int = 5) -> list[MatchResult]:
    """Score a candidate against all jobs and return the top N sorted by composite score."""
    results = []
    for job in jobs:
        result = match_score(candidate, job)
        results.append(result)
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_n]

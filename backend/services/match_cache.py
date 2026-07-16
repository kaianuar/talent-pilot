"""Cache for LLM reasoning scores.

The matching endpoint computes a composite fit score that includes a
"reasoning" component contributed by qwen3-max. That call is expensive
and non-deterministic — re-running /match for the same candidate and
resume would re-rate the same jobs and produce a different score. The
spec (`specs/execution-plan.md:224`) mandates caching the reasoning
scores keyed on `(candidate_id, job_id)`, with the resume content as
the implicit invalidator.

This module:
- computes a stable hash of the candidate's parsed resume
- reads cached reasoning scores for a batch of jobs
- writes fresh reasoning scores after a successful LLM call

A re-uploaded CV produces a different hash, so old cache rows for the
same candidate become invisible to lookups (different key). They sit in
the table until a periodic GC; harmless.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from backend.db import get_session
from backend.models.match_cache import MatchCache


def compute_resume_hash(parsed: dict[str, Any] | None) -> str:
    """Return a stable sha256 of the candidate's parsed resume.

    Used as the cache key together with (candidate_id, job_id). None
    and empty inputs hash to the same value so a candidate with no
    parsed resume doesn't fragment the cache.
    """
    if not parsed:
        return "empty"
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def get_cached_reasoning(
    candidate_id: str,
    resume_hash: str,
    job_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Return cached reasoning info keyed by job_id for the given triple.

    Empty list in -> empty dict out. Any job that isn't in the cache
    is omitted from the result.
    """
    if not job_ids:
        return {}
    with get_session() as session:
        rows = (
            session.query(MatchCache)
            .filter(
                MatchCache.candidate_id == candidate_id,
                MatchCache.resume_hash == resume_hash,
                MatchCache.job_id.in_(job_ids),
            )
            .all()
        )
        return {
            row.job_id: {
                "score": row.reasoning_score,
                "explanation": row.reasoning_explanation or "",
            }
            for row in rows
        }


def cache_reasoning(
    candidate_id: str,
    resume_hash: str,
    job_id: str,
    score: float,
    explanation: str = "",
) -> None:
    """Persist one (candidate, job, resume) -> reasoning row.

    Uses INSERT ... ON CONFLICT REPLACE semantics via a unique
    constraint on (candidate_id, job_id, resume_hash) so re-caching a
    job (e.g. on retry) overwrites the old row rather than erroring.
    """
    with get_session() as session:
        existing = (
            session.query(MatchCache)
            .filter(
                MatchCache.candidate_id == candidate_id,
                MatchCache.resume_hash == resume_hash,
                MatchCache.job_id == job_id,
            )
            .one_or_none()
        )
        if existing is not None:
            existing.reasoning_score = score
            existing.reasoning_explanation = explanation
        else:
            session.add(
                MatchCache(
                    id=str(uuid.uuid4()),
                    candidate_id=candidate_id,
                    job_id=job_id,
                    resume_hash=resume_hash,
                    reasoning_score=score,
                    reasoning_explanation=explanation,
                )
            )

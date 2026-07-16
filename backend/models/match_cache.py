"""Match-cache model.

Caches the LLM reasoning score for a (candidate, job, resume) triple so
re-runs of /match don't re-query qwen3-max. Keyed on a sha256 hash of
the candidate's parsed resume so a re-uploaded CV invalidates the cache
naturally (different hash -> different row).
"""

from sqlalchemy import Column, String, Float, DateTime, UniqueConstraint
from datetime import datetime, timezone

from backend.models.base import Base


class MatchCache(Base):
    __tablename__ = "match_cache"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, nullable=False, index=True)
    job_id = Column(String, nullable=False, index=True)
    # sha256 of the candidate's parsed_resume_json, as a hex string.
    # If the candidate re-uploads a different resume, this changes and
    # the old row becomes invisible to lookups.
    resume_hash = Column(String, nullable=False)
    reasoning_score = Column(Float, nullable=False)
    reasoning_explanation = Column(String, default="")
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", "resume_hash", name="uq_match_cache"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "job_id": self.job_id,
            "resume_hash": self.resume_hash,
            "reasoning_score": self.reasoning_score,
            "reasoning_explanation": self.reasoning_explanation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

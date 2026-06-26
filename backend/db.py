"""Database initialization and session management."""

import json
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.config import DB_PATH, SEED_JOBS_PATH
from backend.models.base import Base
from backend.models.job import Job
from backend.models.candidate import Candidate, ParsedResume
from backend.models.application import Application
from backend.models.audit_log import AuditLogEntry

# Import all models so Base.metadata is populated
import backend.models  # noqa: F401

engine = None
SessionLocal = None


def init_db(db_path: str | Path | None = None):
    """Create all tables if they don't exist."""
    global engine, SessionLocal
    path = db_path or DB_PATH
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", echo=False)
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    return engine


@contextmanager
def get_session() -> Session:
    """Yield a SQLAlchemy session; auto-commits on success, rolls back on error."""
    if SessionLocal is None:
        init_db()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def seed_from_json(path: str | Path | None = None):
    """Load seed jobs from JSON if the jobs table is empty."""
    path = path or SEED_JOBS_PATH
    path = Path(path)
    if not path.exists():
        return 0
    with get_session() as session:
        if session.query(Job).count() > 0:
            return 0  # already seeded
        jobs = json.loads(path.read_text())
        for j in jobs:
            job = Job(
                id=j["id"],
                title=j["title"],
                company=j["company"],
                required_skills_json=json.dumps(j["required_skills"]),
                preferred_skills_json=json.dumps(j.get("preferred_skills", [])),
                min_years=j.get("min_years", 0),
                description=j.get("description", ""),
                recruiter_email=j["recruiter_email"],
                created_at=datetime.fromisoformat(j["created_at"].replace("Z", "+00:00")),
            )
            session.add(job)
        return len(jobs)


def log_audit(
    action: str,
    candidate_id: str | None = None,
    details: dict | None = None,
    status: str = "ok",
):
    """Write an audit log entry."""
    with get_session() as session:
        entry = AuditLogEntry(
            id=str(uuid.uuid4()),
            action=action,
            candidate_id=candidate_id,
            details_json=json.dumps(details or {}),
            status=status,
        )
        session.add(entry)

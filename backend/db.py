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


class DatabaseManager:
    """Manages database connections and sessions.
    
    This class encapsulates database state and provides a clean interface
    for database operations, avoiding global mutable state.
    """
    
    def __init__(self):
        self._engine: Any | None = None
        self._SessionLocal: Any | None = None
        self._db_path: Path | None = None
    
    def init_db(self, db_path: str | Path | None = None) -> Any:
        """Create all tables if they don't exist."""
        from backend.config import DB_PATH
        
        path = db_path or DB_PATH
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        self._db_path = path
        self._engine = create_engine(f"sqlite:///{path}", echo=False)
        self._SessionLocal = sessionmaker(bind=self._engine)
        Base.metadata.create_all(self._engine)
        
        return self._engine
    
    @contextmanager
    def get_session(self) -> Session:
        """Yield a SQLAlchemy session; auto-commits on success, rolls back on error."""
        if self._SessionLocal is None:
            self.init_db()
        
        session = self._SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    @property
    def engine(self) -> Any | None:
        """Get the current engine (if initialized)."""
        return self._engine
    
    @property
    def is_initialized(self) -> bool:
        """Check if database has been initialized."""
        return self._engine is not None and self._SessionLocal is not None


# Global instance for backward compatibility
# In new code, prefer creating your own DatabaseManager instance
_db_manager = DatabaseManager()


def init_db(db_path: str | Path | None = None):
    """Create all tables if they don't exist."""
    return _db_manager.init_db(db_path)


@contextmanager
def get_session() -> Session:
    """Yield a SQLAlchemy session; auto-commits on success, rolls back on error."""
    with _db_manager.get_session() as session:
        yield session


# For backward compatibility with existing code
engine = property(lambda self: _db_manager.engine)
SessionLocal = property(lambda self: _db_manager._SessionLocal if hasattr(_db_manager, '_SessionLocal') else None)


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

"""Job CRUD operations."""

import json
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from backend.db import get_session
from backend.models.job import Job
from backend.models.candidate import Candidate, ParsedResume
from backend.models.application import Application


def list_jobs() -> list[dict]:
    """Return all jobs as dicts."""
    with get_session() as session:
        jobs = session.query(Job).all()
        return [j.to_dict() for j in jobs]


def get_job(job_id: str) -> dict | None:
    """Return a single job by ID, or None."""
    with get_session() as session:
        job = session.query(Job).filter(Job.id == job_id).first()
        return job.to_dict() if job else None


def get_candidate(candidate_id: str) -> dict | None:
    """Return a candidate by ID, or None."""
    with get_session() as session:
        c = session.query(Candidate).filter(Candidate.id == candidate_id).first()
        return c.to_dict() if c else None


def create_candidate(name: str, email: str, phone: str = "", resume_url: str = "") -> dict:
    """Create a candidate and return as dict."""
    cid = str(uuid.uuid4())
    with get_session() as session:
        c = Candidate(id=cid, name=name, email=email, phone=phone, resume_url=resume_url)
        session.add(c)
        session.flush()
        return c.to_dict()


def save_parsed_resume(candidate_id: str, parsed: dict) -> dict:
    """Save or update a parsed resume for a candidate."""
    with get_session() as session:
        existing = session.query(ParsedResume).filter(ParsedResume.candidate_id == candidate_id).first()
        if existing:
            existing.name = parsed["name"]
            existing.email = parsed["email"]
            existing.phone = parsed.get("phone", "")
            existing.skills = parsed.get("skills", [])
            existing.experiences = parsed.get("experiences", [])
            existing.education = parsed.get("education", [])
            existing.years_experience = parsed.get("years_experience", 0)
            existing.parsed_at = datetime.utcnow()
            return existing.to_dict()
        pr = ParsedResume(
            candidate_id=candidate_id,
            name=parsed["name"],
            email=parsed["email"],
            phone=parsed.get("phone", ""),
            skills=parsed.get("skills", []),
            experiences=parsed.get("experiences", []),
            education=parsed.get("education", []),
            years_experience=parsed.get("years_experience", 0),
        )
        session.add(pr)
        return pr.to_dict()


def get_parsed_resume(candidate_id: str) -> dict | None:
    """Return parsed resume for a candidate, or None."""
    with get_session() as session:
        pr = session.query(ParsedResume).filter(ParsedResume.candidate_id == candidate_id).first()
        return pr.to_dict() if pr else None


def create_application(
    candidate_id: str,
    job_id: str,
    match_score: float,
    match_tier: str,
    screening_answers: dict | None = None,
    status: str = "pending",
) -> dict:
    """Create an application record."""
    aid = str(uuid.uuid4())
    with get_session() as session:
        app = Application(
            id=aid,
            candidate_id=candidate_id,
            job_id=job_id,
            match_score=match_score,
            match_tier=match_tier,
            screening_answers=screening_answers or {},
            status=status,
        )
        session.add(app)
        session.flush()
        return app.to_dict()


def get_application(application_id: str) -> dict | None:
    """Return an application by ID."""
    with get_session() as session:
        a = session.query(Application).filter(Application.id == application_id).first()
        return a.to_dict() if a else None


def update_application(application_id: str, **kwargs) -> dict | None:
    """Update an application record."""
    with get_session() as session:
        a = session.query(Application).filter(Application.id == application_id).first()
        if not a:
            return None
        for key, value in kwargs.items():
            if key == "screening_answers":
                a.screening_answers = value
            elif hasattr(a, key):
                setattr(a, key, value)
        session.flush()
        return a.to_dict()

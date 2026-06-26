"""Tests for Phase 1: Job CRUD operations."""

import json
import os
import pytest
import tempfile
from pathlib import Path

# Use a temp DB for tests
# QWEN_API_KEY loaded from .env via dotenv in config.py

from backend.db import init_db, seed_from_json, get_session
from backend.models.job import Job
from backend.services import list_jobs, get_job, create_candidate, get_candidate, create_application, get_application, update_application


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    """Create a fresh DB for each test."""
    db_path = tmp_path / "test.db"
    seed_path = Path(__file__).parent.parent / "data" / "seed_jobs.json"
    init_db(db_path)
    if seed_path.exists():
        seed_from_json(seed_path)
    yield
    # Cleanup happens automatically with tmp_path


def test_seed_jobs_loaded():
    """Seed jobs should be loaded from JSON."""
    jobs = list_jobs()
    assert len(jobs) >= 30, f"Expected 30+ jobs, got {len(jobs)}"


def test_list_jobs_returns_dicts():
    """list_jobs should return a list of dicts with required fields."""
    jobs = list_jobs()
    assert isinstance(jobs, list)
    assert len(jobs) > 0
    for job in jobs[:5]:
        assert "id" in job
        assert "title" in job
        assert "company" in job
        assert "required_skills" in job
        assert isinstance(job["required_skills"], list)


def test_get_job_existing():
    """get_job should return the job for a valid ID."""
    jobs = list_jobs()
    job_id = jobs[0]["id"]
    job = get_job(job_id)
    assert job is not None
    assert job["id"] == job_id
    assert "title" in job
    assert "required_skills" in job


def test_get_job_nonexistent():
    """get_job should return None for an invalid ID."""
    job = get_job("nonexistent-id-12345")
    assert job is None


def test_create_candidate():
    """create_candidate should create and return a candidate."""
    candidate = create_candidate(
        name="Test User",
        email="test@example.com",
        phone="+1-555-0123",
        resume_url="/tmp/test.pdf",
    )
    assert candidate["name"] == "Test User"
    assert candidate["email"] == "test@example.com"
    assert "id" in candidate


def test_get_candidate():
    """get_candidate should retrieve a created candidate."""
    created = create_candidate(name="Jane Doe", email="jane@example.com")
    fetched = get_candidate(created["id"])
    assert fetched is not None
    assert fetched["name"] == "Jane Doe"


def test_get_candidate_nonexistent():
    """get_candidate should return None for unknown IDs."""
    assert get_candidate("nonexistent") is None


def test_create_application():
    """create_application should create and return an application."""
    candidate = create_candidate(name="Applicant", email="app@test.com")
    jobs = list_jobs()
    app = create_application(
        candidate_id=candidate["id"],
        job_id=jobs[0]["id"],
        match_score=0.85,
        match_tier="STRONG_MATCH",
        screening_answers={"Q1": "Yes"},
    )
    assert app["candidate_id"] == candidate["id"]
    assert app["job_id"] == jobs[0]["id"]
    assert app["match_score"] == 0.85
    assert app["status"] == "pending"


def test_get_application():
    """get_application should retrieve a created application."""
    candidate = create_candidate(name="App2", email="app2@test.com")
    jobs = list_jobs()
    created = create_application(
        candidate_id=candidate["id"],
        job_id=jobs[0]["id"],
        match_score=0.7,
        match_tier="PARTIAL_MATCH",
    )
    fetched = get_application(created["id"])
    assert fetched is not None
    assert fetched["id"] == created["id"]


def test_update_application():
    """update_application should modify fields."""
    candidate = create_candidate(name="App3", email="app3@test.com")
    jobs = list_jobs()
    app = create_application(
        candidate_id=candidate["id"],
        job_id=jobs[0]["id"],
        match_score=0.6,
        match_tier="PARTIAL_MATCH",
    )
    updated = update_application(app["id"], status="sent", email_message_id="msg-123")
    assert updated["status"] == "sent"
    assert updated["email_message_id"] == "msg-123"


def test_jobs_have_required_fields():
    """All seed jobs should have the required fields for matching."""
    jobs = list_jobs()
    for job in jobs:
        assert "required_skills" in job
        assert len(job["required_skills"]) > 0, f"Job {job['id']} has no required_skills"
        for skill in job["required_skills"]:
            assert "name" in skill, f"Skill in job {job['id']} missing 'name'"
        assert "min_years" in job
        assert "recruiter_email" in job

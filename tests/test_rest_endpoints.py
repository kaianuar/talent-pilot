"""Integration tests for REST API endpoints via FastAPI TestClient."""

import io
import json
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from backend.db import init_db, seed_from_json
from backend.app import app
from backend.services.email import EmailSendError

@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    """Create a fresh DB for each test."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    seed_from_json()
    yield


@pytest.fixture()
def client():
    """FastAPI TestClient."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_PARSED_RESUME = {
    "name": "Alice Example",
    "email": "alice@example.com",
    "phone": "+1-555-0100",
    "skills": [
        {"name": "Python", "years": 5, "category": "language"},
        {"name": "FastAPI", "years": 3, "category": "framework"},
    ],
    "experiences": [
        {
            "company": "Acme Corp",
            "title": "Senior Engineer",
            "duration": "2020-2023",
            "summary": "Built APIs",
        }
    ],
    "education": [
        {"institution": "MIT", "degree": "BS Computer Science", "year": 2018}
    ],
    "years_experience": 5,
    "raw_response": "Alice Example ...",
}


def _make_pdf_upload(filename: str = "resume.pdf"):
    """Return a minimal PDF-like UploadFile payload."""
    # Minimal PDF header so the endpoint accepts it
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
    return ("file", (filename, io.BytesIO(pdf_bytes), "application/pdf"))


# ============================================================================
# GET /status
# ============================================================================


def test_get_status(client):
    resp = client.get("/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "api_key_configured" in body
    assert "version" in body


# ============================================================================
# POST /upload
# ============================================================================


@patch("backend.app.parse_resume_from_file", return_value=SAMPLE_PARSED_RESUME)
def test_upload_success(mock_parse, client):
    resp = client.post("/upload", files=[_make_pdf_upload()])
    assert resp.status_code == 200
    body = resp.json()
    assert "candidate_id" in body
    assert body["parsed"]["name"] == "Alice Example"
    assert body["parsed"]["years_experience"] == 5
    mock_parse.assert_called_once()


def test_upload_rejects_non_pdf(client):
    resp = client.post(
        "/upload",
        files=[("file", ("resume.txt", io.BytesIO(b"not a pdf"), "text/plain"))],
    )
    assert resp.status_code == 400
    assert "PDF" in resp.json()["detail"]


@patch("backend.app.parse_resume_from_file")
def test_upload_parse_failure(mock_parse, client):
    from backend.services.resume_parser import ResumeParseError

    mock_parse.side_effect = ResumeParseError("bad pdf")
    resp = client.post("/upload", files=[_make_pdf_upload()])
    assert resp.status_code == 400
    assert "parse" in resp.json()["detail"].lower()


@patch("backend.app.parse_resume_from_file", return_value=SAMPLE_PARSED_RESUME)
def test_upload_backfills_candidate_with_parsed_name_and_email(mock_parse, client):
    """Regression: after upload, GET /candidates/{id} must return the parsed
    name and email, not the placeholder filename / 'pending@upload.local'.
    The Candidate row is created with placeholders before parsing; without
    an explicit backfill step, the frontend profile card would show the
    placeholder.
    """
    resp = client.post("/upload", files=[_make_pdf_upload("alice-resume.pdf")])
    assert resp.status_code == 200
    candidate_id = resp.json()["candidate_id"]

    detail = client.get(f"/candidates/{candidate_id}")
    assert detail.status_code == 200
    body = detail.json()

    assert body["name"] == "Alice Example", f"expected parsed name, got {body['name']!r}"
    assert body["email"] == "alice@example.com", f"expected parsed email, got {body['email']!r}"
    assert body["phone"] == "+1-555-0100"
    # The filename placeholder should not have leaked into the row.
    assert "alice-resume.pdf" not in (body["name"] or "")
    assert body["email"] != "pending@upload.local"


# ============================================================================
# POST /chat
# ============================================================================


@patch("backend.app.OpenAI")
def test_chat_success(mock_openai_cls, client):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello! How can I help?"
    mock_client.chat.completions.create.return_value = mock_response

    resp = client.post(
        "/chat",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["assistant_text"] == "Hello! How can I help?"
    assert len(body["messages"]) == 2  # user + assistant


@patch("backend.app.OpenAI")
def test_chat_with_send_confirmed(mock_openai_cls, client):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Application processing!"
    mock_client.chat.completions.create.return_value = mock_response

    resp = client.post(
        "/chat",
        json={
            "messages": [{"role": "user", "content": "Send it"}],
            "send_confirmed": True,
        },
    )
    assert resp.status_code == 200
    # Verify the system prompt about confirmation was appended
    call_args = mock_client.chat.completions.create.call_args
    messages_sent = call_args.kwargs["messages"] if call_args.kwargs else call_args[1]["messages"]
    system_msgs = [m for m in messages_sent if m["role"] == "system"]
    assert any("confirmed" in m["content"].lower() for m in system_msgs)


@patch("backend.app.QWEN_API_KEY", "")
def test_chat_no_api_key(client):
    resp = client.post(
        "/chat",
        json={"messages": [{"role": "user", "content": "Hi"}]},
    )
    assert resp.status_code == 503
    assert "not configured" in resp.json()["detail"].lower()


@patch("backend.app.OpenAI")
def test_chat_api_error(mock_openai_cls, client):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.side_effect = RuntimeError("API down")

    resp = client.post(
        "/chat",
        json={"messages": [{"role": "user", "content": "Hi"}]},
    )
    assert resp.status_code == 502


# ============================================================================
# POST /match
# ============================================================================


@patch("backend.app.list_jobs")
@patch("backend.app.get_parsed_resume")
@patch("backend.app.get_candidate")
def test_match_success(mock_get_cand, mock_get_parsed, mock_list_jobs, client):
    mock_get_cand.return_value = {"id": "c1", "name": "Alice"}
    mock_get_parsed.return_value = {
        "skills": [{"name": "Python", "years": 5}],
        "years_experience": 5,
    }
    mock_list_jobs.return_value = [
        {
            "id": "j1",
            "title": "Backend Engineer",
            "required_skills": ["Python", "FastAPI"],
            "preferred_skills": ["Docker"],
            "min_years": 3,
            "recruiter_email": "hr@example.com",
        }
    ]

    resp = client.post("/match", json={"candidate_id": "c1"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["matches"]) == 1
    assert body["matches"][0]["job_id"] == "j1"
    assert body["matches"][0]["tier"] in (
        "STRONG_MATCH", "PARTIAL_MATCH", "POOR_MATCH", "NO_MATCH"
    )


@patch("backend.app.get_candidate", return_value=None)
def test_match_candidate_not_found(mock_get_cand, client):
    resp = client.post("/match", json={"candidate_id": "nonexistent"})
    assert resp.status_code == 404


# ============================================================================
# GET /candidates/{candidate_id}
# ============================================================================


@patch("backend.app.get_parsed_resume")
@patch("backend.app.get_candidate")
def test_get_candidate_found(mock_get_cand, mock_get_parsed, client):
    mock_get_cand.return_value = {
        "id": "c1",
        "name": "Alice",
        "email": "alice@example.com",
        "phone": "",
        "resume_url": "",
        "created_at": "2024-01-01T00:00:00",
    }
    mock_get_parsed.return_value = {
        "skills": [{"name": "Python"}],
        "years_experience": 5,
        "education": [],
        "experiences": [],
        "certifications": [],
        "raw_response": "raw",
    }

    resp = client.get("/candidates/c1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Alice"
    assert body["years_experience"] == 5
    assert isinstance(body["skills"], list)


@patch("backend.app.get_candidate", return_value=None)
def test_get_candidate_not_found(mock_get_cand, client):
    resp = client.get("/candidates/nonexistent")
    assert resp.status_code == 404


# ============================================================================
# POST /applications
# ============================================================================


@patch("backend.app.update_application")
@patch("backend.app.send_email", return_value="<msg-id-123>")
@patch("backend.app.create_application")
@patch("backend.app.get_job")
def test_application_with_send_confirmed(
    mock_get_job, mock_create_app, mock_send_email, mock_update, client
):
    mock_get_job.return_value = {
        "id": "j1",
        "title": "Backend Engineer",
        "recruiter_email": "hr@example.com",
    }
    mock_create_app.return_value = {
        "id": "a1",
        "candidate_id": "c1",
        "job_id": "j1",
        "status": "sending",
    }

    resp = client.post(
        "/applications",
        json={
            "candidate_id": "c1",
            "job_id": "j1",
            "draft": {
                "match_score": 0.85,
                "match_tier": "STRONG_MATCH",
                "subject": "Application",
                "body": "Dear HR...",
                "to": "hr@example.com",
            },
            "send_confirmed": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "sent"
    assert body["message_id"] == "<msg-id-123>"
    mock_send_email.assert_called_once()


def test_application_without_send_confirmed(client):
    resp = client.post(
        "/applications",
        json={
            "candidate_id": "c1",
            "job_id": "j1",
            "draft": {"subject": "Hi", "body": "..."},
            "send_confirmed": False,
        },
    )
    assert resp.status_code == 403
    assert "send_confirmed" in resp.json()["detail"].lower()


@patch("backend.app.send_email", side_effect=EmailSendError("SMTP not configured"))
@patch("backend.app.update_application")
@patch("backend.app.create_application")
@patch("backend.app.get_job")
def test_application_email_failure(
    mock_get_job, mock_create_app, mock_update, mock_send_email, client
):
    mock_get_job.return_value = {
        "id": "j1",
        "title": "Backend Engineer",
        "recruiter_email": "hr@example.com",
    }
    mock_create_app.return_value = {
        "id": "a1",
        "candidate_id": "c1",
        "job_id": "j1",
        "status": "sending",
    }

    resp = client.post(
        "/applications",
        json={
            "candidate_id": "c1",
            "job_id": "j1",
            "draft": {
                "match_score": 0.5,
                "match_tier": "PARTIAL_MATCH",
                "subject": "Application",
                "body": "Dear HR...",
            },
            "send_confirmed": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert "not configured" in body["error"].lower()


@patch("backend.app.get_job", return_value=None)
def test_application_job_not_found(mock_get_job, client):
    resp = client.post(
        "/applications",
        json={
            "candidate_id": "c1",
            "job_id": "nonexistent",
            "draft": {},
            "send_confirmed": True,
        },
    )
    assert resp.status_code == 404


# ============================================================================
# GET /jobs, GET /jobs/{job_id}
# ============================================================================


def test_list_jobs(client):
    resp = client.get("/jobs")
    assert resp.status_code == 200
    jobs = resp.json()
    assert isinstance(jobs, list)
    assert len(jobs) >= 1


def test_get_single_job(client):
    # First get a valid job id from the seeded data
    jobs = client.get("/jobs").json()
    job_id = jobs[0]["id"]
    resp = client.get(f"/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id


def test_get_single_job_not_found(client):
    resp = client.get("/jobs/nonexistent-job-id")
    assert resp.status_code == 404


# ============================================================================
# GET /audit-log
# ============================================================================


def test_audit_log(client):
    resp = client.get("/audit-log")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_audit_log_with_limit(client):
    resp = client.get("/audit-log?limit=5")
    assert resp.status_code == 200


# ============================================================================
# POST /admin/reseed
# ============================================================================


def test_admin_reseed(client):
    resp = client.post("/admin/reseed")
    assert resp.status_code == 200
    assert "seeded" in resp.json()

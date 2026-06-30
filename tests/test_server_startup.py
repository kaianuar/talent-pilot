"""Smoke tests: verify the server starts cleanly without import or dependency errors."""

import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


# Suppress gRPC server startup in lifespan during testing
@pytest.fixture(autouse=True)
def mock_grpc_server():
    """Prevent gRPC server from starting during tests."""
    with patch("backend.app._grpc_available", False):
        yield


@pytest.fixture
def client():
    """Create a TestClient against the real module-level app."""
    # Import app at module level — triggers lifespan but gRPC is mocked
    from backend.app import app
    with TestClient(app) as tc:
        yield tc


class TestServerStartup:
    """Verify the app starts and endpoints respond."""

    def test_app_imports_without_error(self):
        """Importing backend.app should succeed without ImportError."""
        from backend.app import app
        assert app is not None
        assert app.title == "TalentPilot API"

    def test_status_endpoint(self, client):
        """GET /status should return 200 with expected fields."""
        response = client.get("/status")
        assert response.status_code == 200
        data = response.json()
        assert "api_key_configured" in data
        assert "smtp_configured" in data
        assert "grpc_server_running" in data
        assert "version" in data
        assert isinstance(data["api_key_configured"], bool)
        assert isinstance(data["version"], str)

    def test_jobs_endpoint(self, client):
        """GET /jobs should return a list of seeded jobs."""
        response = client.get("/jobs")
        assert response.status_code == 200
        jobs = response.json()
        assert isinstance(jobs, list)
        assert len(jobs) >= 30, f"Expected >= 30 seeded jobs, got {len(jobs)}"
        assert "id" in jobs[0]
        assert "title" in jobs[0]

    def test_candidates_404_for_unknown(self, client):
        """GET /candidates/{id} should return 404 for unknown IDs."""
        response = client.get("/candidates/nonexistent-id")
        assert response.status_code == 404

    def test_audit_log_endpoint(self, client):
        """GET /audit-log should return 200 with an array."""
        response = client.get("/audit-log")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_match_endpoint_404_for_unknown_candidate(self, client):
        """POST /match should return 404 for unknown candidate."""
        response = client.post("/match", json={"candidate_id": "nonexistent"})
        assert response.status_code == 404


class TestImportSanity:
    """Verify all critical modules import without errors."""

    def test_backend_config_imports(self):
        from backend.config import (
            API_HOST, API_PORT, QWEN_API_KEY, QWEN_BASE_URL,
            MODEL_REASONING, MODEL_CHAT, MODEL_VISION,
        )
        assert isinstance(API_PORT, int)

    def test_backend_db_imports(self):
        from backend.db import init_db, get_session
        assert callable(init_db)

    def test_backend_services_import(self):
        from backend.services import (
            list_jobs, get_job, get_candidate,
            create_candidate, save_parsed_resume,
            create_application, update_application,
        )
        jobs = list_jobs()
        assert isinstance(jobs, list)
        assert len(jobs) >= 30

    def test_backend_models_import(self):
        from backend.models.job import Job
        from backend.models.candidate import Candidate, ParsedResume
        from backend.models.application import Application
        from backend.models.audit_log import AuditLogEntry
        assert Job.__tablename__ == "jobs"

    def test_resume_parser_imports(self):
        from backend.services.resume_parser import parse_resume, ResumeParseError
        assert callable(parse_resume)

    def test_email_service_imports(self):
        from backend.services.email import send_email, EmailSendError
        assert callable(send_email)

    def test_openai_client_available(self):
        from openai import OpenAI
        assert OpenAI is not None

    def test_httpx_available(self):
        import httpx
        assert httpx is not None

    def test_grpc_package_available(self):
        import grpc
        assert grpc is not None

    def test_websockets_package_available(self):
        import websockets
        assert websockets is not None

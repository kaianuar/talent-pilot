"""FastAPI backend for TalentPilot."""

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.db import init_db, seed_from_json, log_audit, get_session
from backend.models.audit_log import AuditLogEntry
from backend.services import (
    list_jobs,
    get_job,
    create_candidate,
    save_parsed_resume,
    get_parsed_resume,
    create_application,
    update_application,
)
from backend.services.resume_parser import parse_resume, ResumeParseError
from backend.services.email import send_email, EmailSendError
from backend.agent.orchestrator import run_turn
from backend.config import API_HOST, API_PORT, SMTP_USER, SMTP_PASS, QWEN_API_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB and seed jobs."""
    init_db()
    count = seed_from_json()
    if count:
        logger.info("Seeded %d jobs", count)
    yield


app = FastAPI(title="TalentPilot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response models ---

class ChatRequest(BaseModel):
    messages: list[dict]
    candidate_id: str
    pdf_path: str | None = None
    send_confirmed: bool = False


class ChatResponse(BaseModel):
    messages: list[dict]
    assistant_text: str


class UploadResponse(BaseModel):
    candidate_id: str
    parsed: dict
    pdf_path: str


class ApplicationRequest(BaseModel):
    candidate_id: str
    job_id: str
    draft: dict
    send_confirmed: bool = False


class ApplicationResponse(BaseModel):
    status: str
    message_id: str | None = None
    error: str | None = None


# --- Endpoints ---

@app.get("/status")
async def get_status():
    """Return service configuration status."""
    return {
        "api_key_configured": bool(QWEN_API_KEY),
        "smtp_configured": bool(SMTP_USER and SMTP_PASS),
        "version": "1.0.0",
    }

@app.post("/upload", response_model=UploadResponse)
async def upload_cv(file: UploadFile = File(...)):
    """Upload a CV PDF and parse it."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted.")

    # Save to disk
    upload_dir = Path("data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    pdf_path = upload_dir / f"{file_id}.pdf"
    content = await file.read()
    pdf_path.write_bytes(content)

    # Parse
    try:
        parsed = parse_resume(content)
    except ResumeParseError as e:
        log_audit(action="resume_parse_failed", details={"error": str(e)}, status="failed")
        raise HTTPException(422, f"Could not parse resume: {e}")

    # Create candidate
    candidate = create_candidate(
        name=parsed.get("name", "Unknown"),
        email=parsed.get("email", ""),
        phone=parsed.get("phone", ""),
        resume_url=str(pdf_path),
    )
    save_parsed_resume(candidate["id"], parsed)

    log_audit(
        action="resume_uploaded",
        candidate_id=candidate["id"],
        details={"filename": file.filename, "skills_count": len(parsed.get("skills", []))},
    )

    return UploadResponse(candidate_id=candidate["id"], parsed=parsed, pdf_path=str(pdf_path))


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Run one conversation turn through the agent."""
    try:
        updated_messages, assistant_text = run_turn(
            messages=req.messages,
            candidate_id=req.candidate_id,
            pdf_path=req.pdf_path,
            send_confirmed=req.send_confirmed,
        )
    except Exception as e:
        logger.exception("Chat turn failed")
        log_audit(action="chat_error", candidate_id=req.candidate_id, details={"error": str(e)}, status="failed")
        raise HTTPException(500, f"Agent error: {e}")

    log_audit(
        action="chat_turn",
        candidate_id=req.candidate_id,
        details={"user_message": req.messages[-1]["content"] if req.messages else "", "assistant_preview": assistant_text[:200]},
    )

    return ChatResponse(messages=updated_messages, assistant_text=assistant_text)


@app.get("/jobs")
async def get_jobs():
    """List all available jobs."""
    return list_jobs()


@app.get("/jobs/{job_id}")
async def get_single_job(job_id: str):
    """Get a specific job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.post("/applications", response_model=ApplicationResponse)
async def submit_application(req: ApplicationRequest):
    """Submit an application — only sends email if send_confirmed=True."""
    if not req.send_confirmed:
        log_audit(
            action="application_rejected_no_confirmation",
            candidate_id=req.candidate_id,
            details={"job_id": req.job_id},
            status="rejected",
        )
        raise HTTPException(403, "send_confirmed must be True to send the application email.")

    # Get job for recruiter email
    job = get_job(req.job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    # Create application record
    application = create_application(
        candidate_id=req.candidate_id,
        job_id=req.job_id,
        match_score=req.draft.get("match_score", 0.0),
        match_tier=req.draft.get("match_tier", "UNKNOWN"),
        screening_answers=req.draft.get("screening_answers", {}),
        status="sending",
    )

    # Send email
    try:
        message_id = send_email(
            to=req.draft.get("to", job["recruiter_email"]),
            subject=req.draft.get("subject", f"Application for {job['title']}"),
            body=req.draft.get("body", ""),
            candidate_id=req.candidate_id,
        )
        update_application(application["id"], status="sent", email_message_id=message_id)
        log_audit(
            action="application_sent",
            candidate_id=req.candidate_id,
            details={"job_id": req.job_id, "message_id": message_id},
            status="sent",
        )
        return ApplicationResponse(status="sent", message_id=message_id)
    except EmailSendError as e:
        update_application(application["id"], status="failed", email_error=str(e))
        log_audit(
            action="application_failed",
            candidate_id=req.candidate_id,
            details={"job_id": req.job_id, "error": str(e)},
            status="failed",
        )
        return ApplicationResponse(status="failed", error=str(e))


@app.get("/audit-log")
async def get_audit_log(limit: int = 20, candidate_id: str | None = None):
    """Get recent audit log entries."""
    with get_session() as session:
        query = session.query(AuditLogEntry).order_by(AuditLogEntry.timestamp.desc())
        if candidate_id:
            query = query.filter(AuditLogEntry.candidate_id == candidate_id)
        entries = query.limit(limit).all()
        return [e.to_dict() for e in entries]


@app.post("/admin/reseed")
async def reseed():
    """Re-seed the database with jobs."""
    from backend.models.job import Job
    with get_session() as session:
        session.query(Job).delete()
    count = seed_from_json()
    return {"seeded": count}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)

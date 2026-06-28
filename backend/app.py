"""FastAPI backend for TalentPilot with gRPC and WebSocket support."""

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Database and models
from backend.db import init_db, seed_from_json, log_audit, get_session
from backend.models.audit_log import AuditLogEntry

# Services
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

# gRPC and WebSocket imports
from backend.infrastructure.grpc.server import GRPCServer, start_dual_server
from backend.infrastructure.grpc.servicer import ScreeningServicer
from backend.infrastructure.websocket.manager import ConnectionManager
from backend.infrastructure.websocket.routes import router as websocket_router

# Config
from backend.config import API_HOST, API_PORT, SMTP_USER, SMTP_PASS, QWEN_API_KEY


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Global gRPC server instance
_grpc_server: Optional[GRPCServer] = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application with gRPC and WebSocket support."""
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Application lifespan manager - handles startup and shutdown."""
        global _grpc_server
        
        # Startup
        logger.info("=" * 60)
        logger.info("TalentPilot API Starting Up...")
        logger.info("=" * 60)
        
        # Initialize database
        init_db()
        count = seed_from_json()
        if count:
            logger.info(f"✅ Seeded {count} jobs")
        
        # Start gRPC server
        logger.info("🚀 Starting gRPC server on port 50051...")
        _grpc_server = GRPCServer(
            host="0.0.0.0",
            port=50051,
            max_workers=10,
        )
        _grpc_server.start()
        logger.info("✅ gRPC server started successfully")
        
        logger.info("✅ TalentPilot API ready")
        logger.info("=" * 60)
        
        yield
        
        # Shutdown
        logger.info("=" * 60)
        logger.info("TalentPilot API Shutting Down...")
        logger.info("=" * 60)
        
        # Stop gRPC server
        if _grpc_server:
            logger.info("🛑 Stopping gRPC server...")
            _grpc_server.stop(grace_period=30.0)
            logger.info("✅ gRPC server stopped")
        
        logger.info("✅ TalentPilot API shutdown complete")
        logger.info("=" * 60)
    
    # Create FastAPI app
    app = FastAPI(
        title="TalentPilot API",
        description="AI-powered recruitment screening API with gRPC and WebSocket support",
        version="2.0.0",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include WebSocket routes
    app.include_router(websocket_router)
    
    return app


# Create the app instance
app = create_app()


# ============================================================================
# Request/Response Models
# ============================================================================

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


# ============================================================================
# REST API Endpoints
# ============================================================================

@app.get("/status")
async def get_status():
    """Return service configuration status."""
    return {
        "api_key_configured": bool(QWEN_API_KEY),
        "smtp_configured": bool(SMTP_USER and SMTP_PASS),
        "grpc_server_running": _grpc_server is not None,
        "version": "2.0.0",
    }


@app.post("/upload", response_model=UploadResponse)
async def upload_cv(file: UploadFile = File(...)):
    """Upload a CV PDF and parse it."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")
    
    candidate = create_candidate(name=file.filename)
    
    pdf_path = Path("uploads") / f"{candidate['id']}.pdf"
    pdf_path.parent.mkdir(exist_ok=True)
    
    with open(pdf_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    try:
        parsed = parse_resume(str(pdf_path))
        save_parsed_resume(candidate["id"], parsed)
    except ResumeParseError as e:
        raise HTTPException(400, f"Failed to parse resume: {e}")
    
    log_audit(
        action="resume_uploaded",
        candidate_id=candidate["id"],
        details={"filename": file.filename, "skills_count": len(parsed.get("skills", []))},
    )
    
    return UploadResponse(candidate_id=candidate["id"], parsed=parsed, pdf_path=str(pdf_path))


# NOTE: /chat endpoint has been replaced by gRPC ScreeningService
# Use StartScreening, SubmitAnswer, and GetNextQuestion gRPC methods instead


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
    
    job = get_job(req.job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    
    application = create_application(
        candidate_id=req.candidate_id,
        job_id=req.job_id,
        match_score=req.draft.get("match_score", 0.0),
        match_tier=req.draft.get("match_tier", "UNKNOWN"),
        screening_answers=req.draft.get("screening_answers", {}),
        status="sending",
    )
    
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

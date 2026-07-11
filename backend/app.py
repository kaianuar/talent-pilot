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
    get_candidate,
    create_candidate,
    save_parsed_resume,
    get_parsed_resume,
    create_application,
    update_application,
)
from backend.services.resume_parser import parse_resume_from_file, ResumeParseError
from backend.services.email import send_email, EmailSendError

# gRPC and WebSocket imports — gRPC is optional (proto may not be compiled)
try:
    from backend.infrastructure.grpc.server import GRPCServer, start_dual_server
    from backend.infrastructure.grpc.servicer import ScreeningServicer
    _grpc_available = True
except ImportError:
    GRPCServer = None  # type: ignore
    start_dual_server = None  # type: ignore
    ScreeningServicer = None  # type: ignore
    _grpc_available = False
from backend.infrastructure.grpc.web_proxy import GRPCWebProxy
from backend.infrastructure.websocket.manager import ConnectionManager
from backend.infrastructure.websocket.routes import router as websocket_router

from backend.config import (
    API_HOST, API_PORT, SMTP_USER, SMTP_PASS, QWEN_API_KEY,
    QWEN_BASE_URL, MODEL_REASONING, MODEL_CHAT,
    SCORE_STRONG, SCORE_PARTIAL, SCORE_WEAK,
    W_REQUIRED, W_ADJACENT, W_EXPERIENCE, W_REASONING,
)
from openai import OpenAI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Global gRPC server instance (only if gRPC imports succeeded)
_grpc_server: Optional[object] = None


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
        
        # Start gRPC server (optional)
        if _grpc_available:
            logger.info("🚀 Starting gRPC server on port 50051...")
            _grpc_server = GRPCServer(
                host="0.0.0.0",
                port=50051,
                max_workers=10,
            )
            _grpc_server.start()
            logger.info("✅ gRPC server started successfully")
        else:
            logger.info("ℹ️  gRPC server not available (proto not compiled) — REST only mode")
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

    # Include gRPC-Web proxy routes (translates HTTP/1.1 to gRPC for browser clients)
    grpc_web_proxy = GRPCWebProxy(grpc_target="localhost:50051")
    app.include_router(grpc_web_proxy.router)
    app.state.grpc_web_proxy = grpc_web_proxy

    return app


# Create the app instance
app = create_app()


# ============================================================================
# Request/Response Models
# ============================================================================




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
    
    candidate = create_candidate(name=file.filename, email="pending@upload.local")
    
    pdf_path = Path("uploads") / f"{candidate['id']}.pdf"
    pdf_path.parent.mkdir(exist_ok=True)
    
    with open(pdf_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    try:
        parsed = parse_resume_from_file(str(pdf_path))
        save_parsed_resume(candidate["id"], parsed)
    except ResumeParseError as e:
        raise HTTPException(400, f"Failed to parse resume: {e}")
    
    log_audit(
        action="resume_uploaded",
        candidate_id=candidate["id"],
        details={"filename": file.filename, "skills_count": len(parsed.get("skills", []))},
    )
    
    return UploadResponse(candidate_id=candidate["id"], parsed=parsed, pdf_path=str(pdf_path))



# ============================================================================
# Chat & Matching Endpoints
# ============================================================================

class ChatRequest(BaseModel):
    messages: list[dict]
    candidate_id: str | None = None
    send_confirmed: bool = False

class ChatResponse(BaseModel):
    messages: list[dict]
    assistant_text: str

CHAT_SYSTEM_PROMPT = """You are TalentPilot, an AI recruiting assistant. You help candidates:
- Upload their CV and get it parsed
- Find matching job opportunities
- Prepare for screening questions
- Apply to jobs

Be helpful, concise, and professional. If the candidate asks about jobs, check their matches. If they want to apply, guide them through the process. Never send an email without explicit confirmation."""

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """Chat with the TalentPilot agent. Stateless — send_confirmed for prompt context only."""
    if not QWEN_API_KEY:
        raise HTTPException(503, "AI service not configured")

    client = OpenAI(base_url=QWEN_BASE_URL, api_key=QWEN_API_KEY)
    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}] + req.messages

    if req.send_confirmed:
        messages.append({"role": "system", "content": "The user has explicitly confirmed they want to send the application. Acknowledge this and tell them the application is being processed."})

    try:
        response = client.chat.completions.create(
            model=MODEL_CHAT,
            messages=messages,
            temperature=0.7,
            max_tokens=2000,
        )
    except Exception as e:
        logger.error(f"Chat API error: {e}")
        raise HTTPException(502, f"AI service error: {e}")

    assistant_text = response.choices[0].message.content
    return ChatResponse(
        messages=req.messages + [{"role": "assistant", "content": assistant_text}],
        assistant_text=assistant_text,
    )


class MatchRequest(BaseModel):
    candidate_id: str

class MatchResponse(BaseModel):
    matches: list[dict]


def _batch_llm_reasoning(
    skills: list[str], years: float, jobs: list[dict]
) -> dict[str, dict]:
    """Single LLM call to rate candidate-job fit for ALL jobs at once.

    Returns {job_id: {"score": float, "explanation": str}}.
    On any failure, returns empty dict (caller falls back to 0.0).
    """
    if not QWEN_API_KEY or not jobs:
        return {}

    job_summaries = [
        f'{i+1}. "{j["title"]}" — required: {", ".join(s if isinstance(s, str) else s.get("name","") for s in j.get("required_skills", []))}'
        for i, j in enumerate(jobs)
    ]

    prompt = (
        f"Candidate skills: {', '.join(skills) if skills else 'none listed'}\n"
        f"Years of experience: {years:.0f}\n\n"
        f"Rate how well this candidate fits each job (0.0-1.0), considering:\n"
        f"- Depth of experience vs requirements\n"
        f"- Project relevance and trajectory\n"
        f"- Transferable skills and growth potential\n\n"
        f"Jobs:\n" + "\n".join(job_summaries) + "\n\n"
        f'Return JSON: {{"ratings": [{{"id": <number>, "score": <0.0-1.0>, "explanation": "<1 sentence>"}}]}}'
    )

    try:
        client = OpenAI(base_url=QWEN_BASE_URL, api_key=QWEN_API_KEY, timeout=15.0, max_retries=0)
        response = client.chat.completions.create(
            model=MODEL_REASONING,
            messages=[
                {"role": "system", "content": "You are a technical recruiting analyst. Rate candidate-job fit objectively. Reply with JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        ratings = data.get("ratings", data if isinstance(data, list) else [])

        result = {}
        for i, r in enumerate(ratings):
            idx = r.get("id", i + 1) - 1  # 1-indexed to 0-indexed
            if 0 <= idx < len(jobs):
                job_id = jobs[idx]["id"]
                result[job_id] = {
                    "score": max(0.0, min(1.0, float(r.get("score", 0.5)))),
                    "explanation": r.get("explanation", ""),
                }
        return result

    except Exception as e:
        logger.warning("LLM reasoning batch failed: %s — falling back to deterministic-only scores", e)
        return {}

def _compute_match(
    candidate_skills: list[str],
    candidate_years: float,
    job: dict,
    llm_reasoning: dict | None = None,
) -> dict:
    """Compute a match score between a candidate and a job."""
    def _names(skills):
        return [s if isinstance(s, str) else s.get("name", "") for s in skills]
    required = [s.lower() for s in _names(job.get("required_skills", []))]
    nice = [s.lower() for s in _names(job.get("preferred_skills", []))]
    cand_skills_lower = [s.lower() for s in candidate_skills]
    matched_required = [s for s in required if any(
        cs in s or s in cs for cs in cand_skills_lower
    )]
    required_ratio = len(matched_required) / len(required) if required else 1.0

    # Adjacent bonus: nice-to-have skills the candidate has
    matched_nice = [s for s in nice if any(
        cs in s or s in cs for cs in cand_skills_lower
    )]
    adjacent_bonus = len(matched_nice) / len(nice) if nice else 0.0

    # Experience score
    exp_years = candidate_years or 0
    experience_score = min(exp_years / 10.0, 1.0)

    # LLM reasoning score (from batch call)
    reasoning_info = (llm_reasoning or {}).get(job["id"], {})
    reasoning_score = reasoning_info.get("score", 0.0)
    reasoning_explanation = reasoning_info.get("explanation", "")

    # Composite score — all 4 weights (sum to 1.0)
    composite = (
        W_REQUIRED * required_ratio +
        W_ADJACENT * adjacent_bonus +
        W_EXPERIENCE * experience_score +
        W_REASONING * reasoning_score
    )

    # Tier classification
    if composite >= SCORE_STRONG:
        tier = "STRONG_MATCH"
    elif composite >= SCORE_PARTIAL:
        tier = "PARTIAL_MATCH"
    elif composite >= SCORE_WEAK:
        tier = "POOR_MATCH"
    else:
        tier = "NO_MATCH"

    # Build explanation
    explanation = (
        f"Matched {len(matched_required)}/{len(required)} required skills"
        + (f", {len(matched_nice)} nice-to-have skills" if matched_nice else "")
        + f". {exp_years:.1f} years experience."
    )
    if reasoning_explanation:
        explanation += f" LLM: {reasoning_explanation}"

    return {
        "job_id": job["id"],
        "job_title": job["title"],
        "match_score": round(composite, 3),
        "tier": tier,
        "required_match_ratio": round(required_ratio, 3),
        "adjacent_bonus": round(adjacent_bonus, 3),
        "experience_score": round(experience_score, 3),
        "llm_reasoning_score": round(reasoning_score, 3),
        "reasoning_explanation": explanation,
    }

@app.post("/match", response_model=MatchResponse)
async def match_candidate(req: MatchRequest):
    """Match a candidate against all available jobs."""
    candidate = get_candidate(req.candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate not found")

    parsed = get_parsed_resume(req.candidate_id)
    skills = [s.get("name", "") for s in parsed.get("skills", [])] if parsed else []
    years = parsed.get("years_experience", 0) or 0 if parsed else 0

    jobs = list_jobs()

    # Pre-filter: deterministic scores first, then LLM-reason only the top matches
    preliminary = [_compute_match(skills, years, j) for j in jobs]
    preliminary.sort(key=lambda m: m["match_score"], reverse=True)
    top_jobs = [j for j, m in zip(jobs, preliminary) if m["match_score"] >= SCORE_WEAK][:10]

    # Single LLM call for top job ratings only
    llm_reasoning = _batch_llm_reasoning(skills, years, top_jobs) if top_jobs else {}

    matches = [_compute_match(skills, years, j, llm_reasoning) for j in jobs]

    log_audit(
        action="match_computed",
        candidate_id=req.candidate_id,
        details={"jobs_matched": len(matches), "top_score": matches[0]["match_score"] if matches else 0},
    )

    return MatchResponse(matches=matches)


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


@app.get("/candidates/{candidate_id}")
async def get_candidate_endpoint(candidate_id: str):
    """Get a candidate by ID, with merged parsed resume data."""
    candidate = get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(404, "Candidate not found")
    parsed = get_parsed_resume(candidate_id)
    if parsed:
        candidate["years_experience"] = parsed.get("years_experience", 0)
        candidate["skills"] = parsed.get("skills", [])
        candidate["education"] = parsed.get("education", [])
        candidate["experience"] = parsed.get("experiences", [])
        candidate["certifications"] = parsed.get("certifications", [])
        candidate["raw_text"] = parsed.get("raw_response", "")
    return candidate


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

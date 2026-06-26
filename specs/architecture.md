# Architecture Spec

## System Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐
│   Browser   │────▶│   Nginx     │────▶│  Streamlit (8501)   │
│  (Candidate) │     │   (9000)    │     │  Chat UI + Preview  │
└─────────────┘     └──────┬──────┘     └─────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  FastAPI    │
                    │  (8000)     │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
     ┌────────────┐ ┌──────────┐ ┌──────────┐
     │  Resume    │ │ Matching │ │  Email   │
     │  Parser    │ │  Engine  │ │  Service │
     │(Qwen3-VL) │ │(Qwen3-Max)│ │(DirectMail)│
     └────────────┘ └──────────┘ └──────────┘
              │            │            │
              └────────────┼────────────┘
                    ┌──────▼──────┐
                    │  SQLite DB  │
                    └─────────────┘
```

## Component Responsibilities

### Nginx (Port 9000)
- Reverse proxy: `/api/*` → FastAPI (8000), `/` → Streamlit (8501)
- WebSocket passthrough for Streamlit real-time updates
- Single entry point for the container

### FastAPI Backend (Port 8000)
- `POST /upload` — CV upload + Qwen3-VL-Plus parsing
- `POST /chat` — Agent conversation loop
- `GET /jobs` — List all available jobs
- `POST /applications` — Email send with HITL enforcement
- `GET /audit-log` — Transparency log
- `POST /admin/reseed` — Reset database

### Streamlit Frontend (Port 8501)
- Two-column layout: chat (60%) + sidebar (40%)
- Sidebar tabs: Job Matches, Email Preview, Audit Log
- PDF uploader with auto-parse on upload
- "Send to Recruiter" button — sole path to email send

### Qwen Cloud (DashScope International, Singapore)
- **Qwen3-VL-Plus**: Vision model for PDF → structured JSON
- **qwen3-max**: Reasoning model for matching, screening questions, email drafting
- OpenAI-compatible API at `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`

### Alibaba DirectMail
- SMTP at `smtpdm.aliyun.com:465` (SSL)
- Sender domain verification required
- Retry: 3 attempts, exponential backoff (1s, 4s, 16s)

### SQLite Database
- File: `data/recruiter.db`
- Tables: `jobs`, `candidates`, `parsed_resumes`, `applications`, `audit_log`
- Seeded on startup from `data/seed_jobs.json` (32 jobs)

## Data Flow

### Upload CV Flow
```
Browser → POST /upload (PDF)
  → resume_parser.parse_resume(pdf_bytes)
    → Qwen3-VL-Plus (base64 image)
    → ParsedResumeModel validation
    → retry on failure (max 2 attempts)
  → create_candidate() + save_parsed_resume()
  → log_audit("resume_uploaded")
  → return {candidate_id, parsed, pdf_path}
```

### Match & Screen Flow
```
Browser → POST /chat ("Are there suitable jobs?")
  → orchestrator.run_turn(messages, candidate_id)
    → LLM decides to call match_jobs_tool
      → matching.rank_matches(parsed, jobs, top_n=5)
        → per job: required_coverage + adjacent_bonus + experience_score + reasoning_score
      → return top-5 ranked results
    → LLM presents matches to user
  → return {messages, assistant_text}
```

### Email Send Flow (HITL)
```
User clicks "Send to Recruiter" in Streamlit
  → send_confirmed = True
  → POST /applications {candidate_id, job_id, draft, send_confirmed: true}
    → if send_confirmed != true: return 403
    → create_application(status="sending")
    → email.send_email(to, subject, body)
      → SMTP_SSL to smtpdm.aliyun.com:465
      → retry up to 3x with backoff
    → update_application(status="sent", message_id=...)
    → log_audit("application_sent")
    → return {status: "sent", message_id}
```

## Deployment Architecture

```
Alibaba Cloud (Singapore Region)
├── Function Compute (Custom Container)
│   ├── Nginx (9000) ─── HTTP Trigger
│   ├── FastAPI (8000)
│   └── Streamlit (8501)
├── Container Registry (ACR)
├── API Gateway (HTTPS)
└── DirectMail (SMTP)
```

Single container image:
- Python 3.11 slim base
- nginx + uvicorn + streamlit
- start.sh manages all three processes

## Mermaid Source
See `docs/architecture.mmd` for the renderable diagram source.

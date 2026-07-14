# 🎯 TalentPilot — AI Recruiter Agent

> **Qwen Cloud Global AI Hackathon — Track 4: Autopilot Agent**
>
> **Submission deadline: July 20, 2026, 2:00 PM PDT** (extended from July 9 per Devpost).
>
> See the [submission checklist](#-submission-checklist) below for current status.

TalentPilot is an AI-powered recruiting assistant that automates the end-to-end initial candidate screening workflow. Candidates upload their CV through a chat interface, the agent parses it, matches against the company's curated job listings, asks targeted screening questions, and emails the recruiter — all with human-in-the-loop confirmation before sending.

## 🏗️ Architecture

```text
┌─────────────┐     ┌─────────────┐     ┌──────────────────────┐
│   Browser   │────▶│   Nginx     │────▶│  React (Vite)        │
│  (Candidate) │     │   (9000)    │     │  Chat UI + Screening │
└──────┬──────┘     └──────┬──────┘     └──────────────────────┘
       │                   │
       │ gRPC-Web          │ REST /api/*
       │ + WebSocket       │
       │                   │
       │            ┌──────▼──────┐
       │            │  FastAPI    │
       │            │  (8000)     │
       │            └──────┬──────┘
       │                   │
       │     ┌─────────────┼─────────────┐
       │     ▼             ▼             ▼
       │  ┌────────┐ ┌──────────┐ ┌──────────┐
       │  │ Resume │ │ Matching │ │  Email   │
       │  │ Parser │ │  Engine  │ │  Service │
       │  │(Qwen-  │ │(Qwen-Max)│ │(Direct   │
       │  │VL+Turbo│ │          │ │ Mail)    │
       │  └────────┘ └──────────┘ └──────────┘
```

## ✨ Features

- **CV Parsing**: Upload a PDF resume → structured data extraction. Text-extractable PDFs go through `qwen-turbo` (JSON-schema-tuned); scanned/image-only PDFs fall back to `qwen3-vl-plus` (vision model that renders pages to PNG).
- **Smart Matching**: Composite scoring with required skills (35%), adjacent skills (20%), experience (20%), and LLM reasoning (25%) via `qwen3-max`.
- **gRPC Screening Interview**: Multi-turn AI interview via gRPC + LangGraph — asks targeted questions, assesses answers in real-time, drafts recruiter email on completion

- **Screening Questions**: AI-generated questions targeting skill gaps specific to each candidate-job pair
- **Real-time WebSocket Progress**: Live progress updates during the screening interview
- **Email Drafting**: Professional recruiter email drafted by `qwen3-max`, previewed before sending

## 🚀 Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd qwen-hackathon
pip install -r backend/requirements.txt

# 2. Build React frontend (includes proto compilation)
cd frontend-react && npm install && npm run build && cd ..

# 2b. (Optional) Compile gRPC proto for screening
pip install grpcio-tools
python -m grpc_tools.protoc -I backend/infrastructure/grpc \
  --python_out=backend/infrastructure/grpc/proto \
  --grpc_python_out=backend/infrastructure/grpc/proto \
  backend/infrastructure/grpc/screening.proto

# 3. Set your API key
export QWEN_API_KEY="your-qwen-cloud-api-key"

# 4. Start backend (serves API + static frontend)
uvicorn backend.app:app --reload --port 9000

# 5. Open http://localhost:9000
```

```
qwen-hackathon/
├── backend/
│   ├── app.py                  # FastAPI endpoints
│   ├── config.py               # Environment configuration
│   ├── db.py                   # SQLite init + session management
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── base.py             # Shared declarative base
│   │   ├── job.py              # Job model
│   │   ├── candidate.py        # Candidate + ParsedResume
│   │   ├── application.py      # Application tracking
│   │   └── audit_log.py        # Audit trail
│   ├── domain/                 # Ports-and-adapters: core domain
│   │   ├── entities/           # ScreeningSession
│   │   ├── value_objects/      # Question, Assessment
│   │   └── services/           # AnswerAssessor (port interface)
│   ├── application/            # Use cases + port interfaces
│   │   ├── use_cases/          # conduct_screening
│   │   ├── ports/              # QuestionGenerator
│   │   └── services/           # screening_orchestrator
│   ├── infrastructure/         # Adapters + transport
│   │   ├── adapters/           # LLM-backed implementations of ports
│   │   ├── grpc/               # gRPC server, servicer, web proxy
│   │   ├── orchestration/      # LangGraph screening graph
│   │   └── websocket/          # WebSocket progress manager + routes
│   ├── services/               # Cross-cutting business logic
│   │   ├── resume_parser.py    # PDF parsing (qwen-turbo text + qwen-vl-plus vision)
│   │   ├── email.py            # Alibaba DirectMail SMTP
│   │   └── __init__.py         # CRUD: create_candidate, get_candidate, update_candidate, etc.
│   └── requirements.txt
├── frontend-react/
│   ├── src/
│   │   ├── components/         # React UI (ChatInterface, ScreeningPanel, JobMatches, CandidateProfile)
│   │   ├── api/                # API client + gRPC client + React Query hooks
│   │   ├── store/              # Zustand client state
│   │   ├── generated/          # Auto-generated protobuf-ts types
│   │   ├── test/               # Test utilities
│   │   ├── App.tsx             # Root component
│   │   └── main.tsx            # Entry point
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── data/
│   ├── seed_jobs.json          # 32 realistic job listings
│   ├── test_resumes/           # Sample CVs for parser testing
│   ├── recruiter.db            # SQLite (gitignored, created at runtime)
│   └── uploads/                # Uploaded CV PDFs (gitignored, created at runtime)
├── deploy/
│   ├── Dockerfile              # Multi-stage (node build + python runtime)
│   ├── nginx.conf              # Reverse proxy config
│   ├── start.sh                # Container startup script
│   └── deploy.sh               # Alibaba Cloud deployment script
├── tests/                      # Pytest suite (10 files)
│   ├── test_jobs_crud.py       # Data layer
│   ├── test_resume_parser.py   # CV parsing (needs QWEN_API_KEY)
│   ├── test_matching.py        # Matching engine (no LLM needed)
│   ├── test_rest_endpoints.py  # FastAPI integration tests
│   ├── test_answer_assessor.py # LLM answer assessment
│   ├── test_email_service.py   # DirectMail SMTP
│   ├── test_grpc_servicer.py   # gRPC screening service
│   ├── test_grpc_web_proxy.py  # gRPC-Web proxy
│   ├── test_websocket_routes.py# WebSocket progress
│   └── test_server_startup.py  # App + config import smoke tests
├── docs/
│   ├── architecture.mmd        # Mermaid architecture diagram
│   ├── ARCHITECTURE.md         # Architecture narrative
│   ├── ARCHITECTURE_COMPLIANCE_REPORT.md
│   ├── REVIEW_BRIEF.md
│   ├── REVIEW_REPORT.md
│   └── UI_UX_REVIEW_REPORT.md
├── specs/                      # Project specifications
├── AGENTS.md                   # Project conventions for AI agents
├── CLAUDE.md                   # Pointer to AGENTS.md
├── LICENSE                     # MIT License
└── README.md                   # This file
```
## 🧠 Matching Algorithm

The composite match score combines four signals:

```
Score = 0.35 × required_coverage
      + 0.20 × adjacent_bonus
      + 0.20 × experience_score
      + 0.25 × reasoning_score (LLM)
```

| Tier | Score Range | Action |
|------|-------------|--------|
| STRONG_MATCH | ≥ 0.75 | Proceed to screening |
| PARTIAL_MATCH | ≥ 0.55 | Ask clarifying questions |
| WEAK_MATCH | ≥ 0.40 | Ask but warn about gaps |
| NO_MATCH | < 0.40 | Reject with suggestions |

**Adjacent skills** are modeled as a graph: e.g., React↔Vue, PostgreSQL↔MySQL, AWS↔Azure. Candidates with transferable skills get partial credit.

## 🔒 Human-in-the-Loop

The email send is guarded at two levels — the candidate must explicitly opt in before any recruiter contact happens:

1. **API enforcement**: `POST /applications` returns `403` and writes an `application_rejected_no_confirmation` audit entry when `send_confirmed=False`. The email is never sent and no application record is created.
2. **Frontend gating**: The screening result screen shows the email draft and waits. The candidate must click **"Send to Recruiter"** on the result screen, which sets `send_confirmed=True` before submission. Until then, the only path off the result screen is **"Apply for a Different Position"** (or "Back to Chat" for rejected candidates), which both clear the selection without sending.

Never bypass either gate. Never infer `send_confirmed` from context — the explicit click is the contract.

## 🧪 Testing

```bash
# Run the full suite
pytest tests/ -v

# A few targeted runs
pytest tests/test_jobs_crud.py -v          # Data layer (no LLM)
pytest tests/test_matching.py -v           # Matching engine (no LLM)
pytest tests/test_rest_endpoints.py -v     # FastAPI integration (uses tmp DB)
pytest tests/test_resume_parser.py -v      # CV parsing (needs QWEN_API_KEY)
pytest tests/test_grpc_servicer.py -v      # gRPC screening service
pytest tests/test_websocket_routes.py -v   # WebSocket progress
```

## 🌐 Tech Stack

| Component | Technology | Qwen Model |
|-----------|------------|------------|
| CV Parsing (text path) | qwen-turbo | JSON-schema extraction |
| CV Parsing (vision path, scanned PDFs) | qwen3-vl-plus | Vision + OCR |
| Matching Reasoning | qwen3-max | Chat + Reasoning |
| Screening Questions | qwen3-max | Chat + Reasoning |
| Email Drafting | qwen3-max | Chat + Reasoning |
| Backend | FastAPI + SQLAlchemy + LangGraph | — |
| Frontend | React 19 + TypeScript + Vite + Material UI v9 | — |
| gRPC / WebSocket | gRPC-Web proxy + WebSocket progress | — |
| Deployment | Docker (multi-stage) → Alibaba Cloud FC | — |

## 📋 Submission Checklist

- [ ] **Public GitHub repo** — `LICENSE` (MIT) is committed; the repo still needs to be pushed to a public GitHub URL before submission.
- [x] Code repo with open-source license (MIT, committed)
- [x] Architecture diagram (`docs/architecture.mmd`)
- [ ] **Demo video** (~3 min, YouTube/Vimeo, public) — pending recording
- [ ] **Proof of Alibaba Cloud deployment** — Docker build is in `deploy/`; the deployment itself is pending
- [ ] **Devpost submission form** — submitted via the Devpost UI once the video and deployment are live

**Hard deadline: 2:00 PM PDT on July 20, 2026.**

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

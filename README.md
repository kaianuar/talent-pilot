# 🎯 TalentPilot — AI Recruiter Agent

> **Qwen Cloud Global AI Hackathon — Track 4: Autopilot Agent**

TalentPilot is an AI-powered recruiting assistant that automates the end-to-end initial candidate screening workflow. Candidates upload their CV through a chat interface, the agent parses it, matches against the company's curated job listings, asks targeted screening questions, and emails the recruiter — all with human-in-the-loop confirmation before sending.

## 🏗️ Architecture

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

## ✨ Features

- **CV Parsing**: Upload a PDF resume → structured data extraction via Qwen3-VL-Plus vision model
- **Smart Matching**: Composite scoring with required skills (35%), adjacent skills (20%), experience (20%), and LLM reasoning (25%)
- **Screening Questions**: AI-generated questions targeting skill gaps specific to each candidate-job pair
- **Email Drafting**: Professional recruiter email drafted by qwen3-max, previewed before sending
- **Human-in-the-Loop**: Email only sends when the candidate explicitly clicks "Send" — enforced at both prompt and API level
- **Audit Log**: Every action logged for transparency and debugging
- **32 Realistic Jobs**: Seeded dataset spanning backend, frontend, data, devops, mobile, ML, design, QA

## 🚀 Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd qwen-hackathon
pip install -r backend/requirements.txt -r frontend/requirements.txt

# 2. Set your API key
export QWEN_API_KEY="your-qwen-cloud-api-key"

# 3. Start backend
uvicorn backend.app:app --reload --port 9000 &

# 4. Start frontend
streamlit run frontend/streamlit_app.py --server.port 8501

# 5. Open http://localhost:8501
```

## 📁 Project Structure

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
│   ├── services/               # Business logic
│   │   ├── resume_parser.py    # Qwen3-VL-Plus CV parsing
│   │   ├── email.py            # Alibaba DirectMail SMTP
│   │   └── __init__.py         # CRUD operations
│   └── agent/                  # AI agent layer
│       ├── aliases.py          # Skill normalization + adjacency graph
│       ├── matching.py         # Composite match scoring
│       ├── prompts.py          # System prompts
│       ├── tools.py            # 6 MCP-style tools
│       └── orchestrator.py     # Agent loop with tool calling
├── frontend/
│   └── streamlit_app.py        # Chat UI + job matches + email preview
├── data/
│   ├── seed_jobs.json          # 32 realistic job listings
│   └── test_resumes/           # Sample CVs for testing
├── deploy/
│   ├── Dockerfile              # Single-container deployment
│   ├── nginx.conf              # Reverse proxy config
│   ├── start.sh                # Container startup script
│   └── deploy.sh               # Alibaba Cloud deployment script
├── tests/
│   ├── test_jobs_crud.py       # Phase 1: Data layer tests
│   ├── test_resume_parser.py   # Phase 2: CV parsing tests
│   ├── test_matching.py        # Phase 3: Matching engine tests
│   └── test_agent_flow.py      # Phase 4: Agent orchestration tests
├── docs/
│   └── architecture.mmd        # Mermaid architecture diagram
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

The email sending is guarded at two levels:

1. **Agent prompt**: "Never call send_email_tool unless the user has explicitly clicked 'Send'"
2. **API enforcement**: `/applications` endpoint returns 403 if `send_confirmed=False`
3. **Orchestrator code**: `_execute_tool()` blocks `send_email_tool` when `send_confirmed=False`

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific phases
pytest tests/test_jobs_crud.py -v          # Phase 1
pytest tests/test_matching.py -v           # Phase 3 (no LLM needed)
pytest tests/test_resume_parser.py -v      # Phase 2 (needs QWEN_API_KEY)
pytest tests/test_agent_flow.py -v         # Phase 4 (mocked LLM)
```

## 🌐 Tech Stack

| Component | Technology | Qwen Model |
|-----------|------------|------------|
| CV Parsing | Qwen3-VL-Plus | Vision + OCR |
| Matching Reasoning | qwen3-max | Chat + Reasoning |
| Screening Questions | qwen3-max | Chat + Reasoning |
| Email Drafting | qwen3-max | Chat + Reasoning |
| Backend | FastAPI + SQLAlchemy | — |
| Frontend | Streamlit | — |
| Email | Alibaba DirectMail | — |
| Deployment | Alibaba Cloud FC | — |

## 📋 Submission Checklist

- [x] Public GitHub repo with MIT license
- [x] Code repo with open-source license
- [x] Architecture diagram (`docs/architecture.mmd`)
- [ ] Demo video (~3 min, YouTube/Vimeo)
- [ ] Proof of Alibaba Cloud deployment
- [ ] Devpost submission form

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

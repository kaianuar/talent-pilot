# TalentPilot — Executive Summary

## What It Is
An AI-powered recruiter agent that automates end-to-end candidate screening. Candidates upload a CV through a chat interface; the agent parses it, matches against curated job listings, asks targeted screening questions, and emails the recruiter — all with human-in-the-loop confirmation before sending.

## Why It Matters
- Manual resume screening costs recruiters 23 hours per hire on average
- 75% of resumes are disqualified by ATS keyword matching alone, missing transferable skills
- TalentPilot uses LLM reasoning + adjacent-skill modeling to surface hidden fits, then gates the final send behind explicit human confirmation

## Tech Stack

| Layer | Technology | Qwen Model |
|-------|------------|------------|
| CV Parsing | Qwen3-VL-Plus | Vision + OCR |
| Match Reasoning | qwen3-max | Chat + Reasoning |
| Screening Questions | qwen3-max | Chat + Reasoning |
| Email Drafting | qwen3-max | Chat + Reasoning |
| Backend API | FastAPI + SQLAlchemy 2.0 | — |
| Frontend | Streamlit | — |
| Email | Alibaba DirectMail SMTP | — |
| Deployment | Alibaba Cloud Function Compute | — |

## Key Differentiators (for judging)
1. **Adjacent-skill graph**: 150+ skill mappings (e.g., React↔Vue, PostgreSQL↔MySQL) — not just keyword matching
2. **Composite scoring**: 4 signals weighted by importance, not a single LLM call
3. **Defense-in-depth HITL**: prompt guard + API guard + orchestrator code guard — triple enforcement
4. **Rejection with reasoning**: agent tells candidates WHY they don't match and suggests improvements
5. **Full audit trail**: every action logged for transparency

## Build Status

| Phase | Status | Tests |
|-------|--------|-------|
| 0. Repo + seed data | ✅ Done | 32 jobs seeded |
| 1. Data layer | ✅ Done | 11 CRUD tests pass |
| 2. Resume parser | ✅ Done | 6 tests pass (2 LLM tests skip pending real key) |
| 3. Matching engine | ✅ Done | 14 tests pass |
| 4. Agent orchestration | ✅ Done | 9 tests pass |
| 5. Streamlit frontend | ✅ Done | Manual test needed |
| 6. Email service | ✅ Done | Retry logic tested |
| 7. Docker deployment | ✅ Done | Container ready |
| 8. Documentation | ✅ Done | README, diagrams |

## Remaining Work
- [ ] Claim Qwen Cloud voucher and get real API key
- [ ] End-to-end manual test with real LLM
- [ ] Deploy to Alibaba Cloud Function Compute
- [ ] Record 3-minute demo video
- [ ] Submit to Devpost by July 9, 2026 2:00 PM PDT

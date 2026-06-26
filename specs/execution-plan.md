# Recruiter AI Agent — Qwen Cloud Hackathon (Track 4) Plan

## Context

Build an AI agent that automates end-to-end initial candidate screening for a recruiting company. Candidates upload CVs to a chat interface, the agent parses the CV, matches it against the company's curated job listings, asks targeted screening questions, drafts a recruiter email, and sends it only on candidate confirmation. Submitted to the Qwen Cloud Global AI Hackathon, **Track 4: Autopilot Agent**, deadline **July 9, 2026 2:00 PM PDT**. Target outcome: Track 4 grand prize ($7,000 cash + $3,000 cloud credits) or Honorable Mention ($500 + $500). The current project root `~/qwen-hackathon/` contains only an empty `specs/` folder — greenfield.

Per user decision: **Streamlit on Function Compute** for the frontend; **Alibaba DirectMail** for email delivery.

## Approach

Seven ordered build phases. Each phase ends with a verifiable check; later phases depend on working prior ones. Steps are grouped by behavior, not by file.

### Phase 0: Setup & Cloud Accounts (Day 1-2)

**0.1 Initialize repo at `~/qwen-hackathon/`**
- `git init`, add `LICENSE` (MIT — judges require an open-source license visible in the repo's About section per the official rules), Python `.gitignore`, placeholder `README.md`.
- Create the directory structure:
  ```
  backend/{app.py, agent/, services/, models/, db.py, config.py, requirements.txt}
  frontend/{streamlit_app.py, components/, requirements.txt}
  data/{seed_jobs.json, test_resumes/}
  deploy/{Dockerfile, deploy.sh, README.md}
  docs/  (architecture.png, demo_video.mp4, README.md)
  tests/
  specs/
  ```
- Greenfield — no existing code to reuse.

**0.2 Claim Qwen Cloud voucher; set up Alibaba Cloud account**
- Register at https://www.qwencloud.com/challenge/hackathon/voucher-application using the same email as Devpost.
- Create API key at https://home.qwencloud.com/api-keys. Store in `~/.qwen_hackathon.env` as `QWEN_API_KEY=...` and `QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1`.
- Choose **Singapore region** for both Qwen Cloud (DashScope International) and Alibaba Cloud. Singapore has the lowest average latency for international users and is the documented Qwen Cloud international endpoint.

**0.3 Seed `data/seed_jobs.json` with 30+ jobs**
- Each job: `id` (UUID), `title`, `company`, `required_skills` (array of `{name, category, min_years, is_required}`), `preferred_skills`, `min_years`, `description`, `recruiter_email`, `created_at`.
- 5–8 categories: backend, frontend, data, devops, mobile, ML, design, QA. Every required skill must have a `name` and `min_years` — the matcher in Phase 3 rejects malformed jobs.

**Phase 0 check**: `python -c "import json; jobs = json.load(open('data/seed_jobs.json')); assert len(jobs) >= 30; assert all(j['required_skills'] for j in jobs)"` passes. Smoke-test the API: `python -c "from openai import OpenAI; import os; c = OpenAI(base_url=os.environ['QWEN_BASE_URL'], api_key=os.environ['QWEN_API_KEY']); print(c.models.list().data[0].id)"` prints a model name (e.g. `qwen3-max`).

### Phase 1: Data Layer (Day 3-4)

**1.1 SQLAlchemy 2.0 models in `backend/models/`**
- `Job`, `Candidate`, `ParsedResume`, `Application`, `AuditLogEntry`. Pydantic models for input validation alongside SQLAlchemy ORM.
- SQLite file at `data/recruiter.db`. No external DB.

**1.2 `backend/db.py`**
- `init_db()` creates all tables; `get_session()` is a context manager.
- `seed_from_json(path)` loads `seed_jobs.json` on first run, idempotent (skips if jobs already exist).

**1.3 `backend/services/jobs.py`**
- `list_jobs() -> list[Job]`, `get_job(job_id) -> Job`, `create_application(candidate_id, job_id, match_score, screening_answers) -> Application`.

**Phase 1 check**: `pytest tests/test_jobs_crud.py -v` covers create/list/get; `python -c "from backend.db import init_db; init_db(); from backend.services.jobs import list_jobs; assert len(list_jobs()) >= 30"`.

### Phase 2: Resume Parsing Service (Day 5-7)

**2.1 `backend/services/resume_parser.py`**
- `parse_resume(pdf_bytes: bytes) -> ParsedResume` — calls Qwen3-VL-Plus (model id `qwen3-vl-plus`) with the PDF as a base64 image in a multimodal OpenAI-compatible chat completion.
- System prompt: "Extract identity, contact, skills (infer implicit skills from experience descriptions), experience entries with years, education. Return strict JSON matching this schema: {name, email, phone, skills: [{name, years, category}], experiences: [{company, role, start, end, summary}], education: [...], years_experience: int}. No commentary."
- Validate response against the Pydantic `ParsedResume` model. On schema mismatch, retry once with the same prompt plus "Return ONLY the JSON object, no prose." On second failure, raise `ResumeParseError` with a `partial=True` flag — the API returns a 422 to the frontend and shows a "could not parse, please re-upload" message.

**2.2 `tests/test_resume_parser.py`**
- 5 sample CVs in `data/test_resumes/`: clean PDF, scanned image, multi-column layout, no photo, English with mixed-script name. Assert each parse returns non-empty `name`, `email`, ≥3 skills, ≥1 experience.

**Phase 2 check**: `pytest tests/test_resume_parser.py -v` passes 5/5.

### Phase 3: Matching Engine (Day 8-10)

**3.1 `backend/agent/matching.py`**
- `match_score(candidate: ParsedResume, job: Job) -> MatchResult`:
  - `required_coverage` = `count(required_skills matched) / count(required_skills)` — exact string match after lowercasing + alias normalization. Aliases live in `backend/agent/aliases.py` (e.g. `react.js` → `react`, `k8s` → `kubernetes`, `node` → `node.js`).
  - `adjacent_bonus` = `count(required_skills with adjacent match) / count(required_skills) * 0.5` — uses a hand-curated `ADJACENT_SKILLS` dict in the same file (e.g. `go` ↔ `python` for backend roles, `react` ↔ `vue` for frontend, `postgres` ↔ `mysql` for SQL DBs). Deterministic, no LLM call.
  - `experience_score` = `min(1.0, candidate.years_experience / job.min_years)`.
  - `reasoning_score` — single call to `qwen3-max` with prompt: "Given this candidate JSON and this job JSON, rate the fit 0.0-1.0 considering depth of experience, project relevance, and trajectory. Reply with a single decimal number, nothing else." Parse the response.
  - `composite = 0.35 * required_coverage + 0.20 * adjacent_bonus + 0.20 * experience_score + 0.25 * reasoning_score`.
  - Returns `MatchResult(score=composite, tier=...)` where tier is `STRONG_MATCH` (≥0.75), `PARTIAL_MATCH` (≥0.55), `WEAK_MATCH` (≥0.40), `NO_MATCH` (<0.40). Cache the result in `data/recruiter.db` keyed by `(candidate_id, job_id)` — re-runs don't re-call the LLM.
- `rank_matches(candidate, jobs) -> list[MatchResult]` returns top-5 sorted by `composite` descending.

**3.2 `tests/test_matching.py`**
- 12 candidate-job pairs: full match, partial match, adjacent match, under-experienced, over-experienced, irrelevant, edge case at 0.75 boundary, edge case at 0.55 boundary, missing skill alias, multi-skill partial, etc. Assert the tier is correct for each.

**Phase 3 check**: `pytest tests/test_matching.py -v` passes 12/12.

### Phase 4: Agent Orchestration with Qwen-Agent (Day 11-14)

**4.1 `backend/agent/tools.py` — six MCP-style tools**
- `parse_resume_tool(pdf_url) -> dict` — wraps `services.resume_parser.parse_resume`. Returns parsed JSON.
- `list_jobs_tool() -> list[dict]` — wraps `services.jobs.list_jobs`. Returns `[{id, title, company}]`.
- `match_jobs_tool(candidate_id) -> list[dict]` — wraps `matching.rank_matches`. Returns top-5 with scores and reasoning.
- `generate_screening_questions_tool(candidate_id, job_id) -> list[str]` — calls `qwen3-max` with the candidate, the job, and the gap list from the match result. Prompt: "Generate 2-3 targeted screening questions that resolve uncertainty in this candidate-job fit. Focus on the gaps identified. Each question should be answerable in 1-2 sentences. Return as a JSON array of strings."
- `confirm_and_draft_email_tool(candidate_id, job_id, screening_answers) -> dict` — calls `qwen3-max` to draft a concise email `{to, subject, body}` addressed to the recruiter, with the candidate's relevant experience highlighted and a short summary of screening answers. The tool **does not call the email service** — it only returns the draft.
- `send_email_tool(draft, attachment_url=None) -> str` — wraps `services.email.send_email`. Returns DirectMail message ID.
- Every tool is a function with a docstring; Qwen-Agent parses the docstring for the tool description and parameter schema.

**4.2 `backend/agent/orchestrator.py`**
- Instantiate Qwen-Agent `Agent` with model `qwen3-max`, system prompt: "You are TalentPilot, an AI recruiter assistant for [RecruiterCo]. Help candidates find suitable jobs by parsing their CV, matching it to the company's job list, asking 2-3 targeted screening questions, and drafting an email to the recruiter. Always use tools — never guess job IDs or recruiter emails. Never call `send_email_tool` unless the user has explicitly clicked 'Send' on a drafted email in the previous turn. If no jobs match, say so and ask the candidate if they'd like to broaden the search."
- `run_turn(messages: list[dict], candidate_id: str) -> tuple[list[dict], str]` — appends the latest user message, calls `agent.run`, returns updated messages + the final assistant text.

**4.3 Human-in-the-loop gate**
- The agent's system prompt explicitly forbids `send_email_tool` without prior user click. The orchestrator also enforces this at the code level: it inspects the agent's tool calls; if `send_email_tool` is called and `st.session_state.send_confirmed` is False on the request, the orchestrator drops the call and appends a synthetic message "I need your confirmation before sending. Please click 'Send' on the email preview."
- The frontend's "Send to Recruiter" button sets `send_confirmed=True` on the next request.

**4.4 `backend/app.py` — FastAPI**
- `POST /upload` — accepts PDF, stores in `data/uploads/` (local FS; for production deploy, swap to OSS via env flag), calls `parse_resume_tool` server-side, returns `candidate_id` + parsed preview.
- `POST /chat` — accepts `messages` and `candidate_id`, calls `orchestrator.run_turn`, returns updated messages.
- `GET /jobs` — returns all jobs.
- `POST /applications` — accepts `candidate_id`, `job_id`, `draft`, `send_confirmed`. Only calls `send_email_tool` when `send_confirmed=True`. Returns message ID.
- Every endpoint writes an `AuditLogEntry` row with `timestamp`, `action`, `candidate_id`, and a JSON-serialized input/output excerpt.

**Phase 4 check**: `pytest tests/test_agent_flow.py -v` simulates a full conversation (upload → match → screening → confirm → email) with mocked LLM responses, asserts the expected tool sequence and that `send_email_tool` is never called without `send_confirmed=True`.

### Phase 5: Streamlit Frontend (Day 15-17)

**5.1 `frontend/streamlit_app.py`**
- Two-column layout. Left column (60%): chat thread. Right column (40%): sidebar with three tabs.
- **Tab "Job Matches"**: shows top-5 matches as expandable cards (title, company, score, reasoning snippet, "Apply to this one" button that injects a user message into the chat).
- **Tab "Email Preview"**: shown when the agent returns a draft. Renders the `to`, `subject`, `body`. Big "Send to Recruiter" button below — only this button sets `send_confirmed=True`.
- **Tab "Audit Log"**: shows the last 20 `AuditLogEntry` rows for the current session, formatted as a table. Doubles as a transparency demo for judges.
- File uploader at the top of the chat column accepts PDF; on upload, calls `/upload`, then auto-sends "Are there any suitable jobs based on my CV?" as the first user message.
- Chat loop: `st.chat_input` → POST `/chat` → render assistant reply with `st.chat_message`.

**5.2 Streamlit session state**
- `st.session_state.messages` — chat history.
- `st.session_state.candidate_id` — set after upload.
- `st.session_state.email_draft` — set when the agent returns a draft; cleared after send.
- `st.session_state.send_confirmed` — set to `True` only when the user clicks the explicit Send button.

**Phase 5 check**: Manual end-to-end test. Start `uvicorn backend.app:app --reload --port 9000` in one terminal, `streamlit run frontend/streamlit_app.py --server.port 8501` in another. Complete the full flow in a browser. Confirm: upload works, matches appear, screening questions get asked, email preview shows, Send button works, audit log shows the send event.

### Phase 6: Email Integration with DirectMail (Day 18-19)

**6.1 Verify DirectMail access**
- In the Singapore region console: DirectMail → Sender Addresses → add and verify a sender domain. Use a real domain you control, or the Alibaba-provided test sender.
- SMTP credentials (`smtpdm.aliyun.com`, port 465, username, password) stored in `~/.qwen_hackathon.env` as `ALIYUN_SMTP_USER` and `ALIYUN_SMTP_PASS`.
- Send a test email via the console to confirm the sender is active.

**6.2 `backend/services/email.py`**
- `send_email(to, subject, body, attachment_path=None) -> str` — uses Python `smtplib.SMTP_SSL` against `smtpdm.aliyun.com:465`, authenticates, sends a multipart message (plain text body + optional PDF attachment), returns the DirectMail-assigned `Message-ID` header value.
- On failure: retry up to 3 times with exponential backoff (1s, 4s, 16s). On final failure, raise `EmailSendError`; the API endpoint catches it, writes an `AuditLogEntry` with `status="failed"`, and returns a 502 to the frontend.

**6.3 Wire the Send button**
- The "Send to Recruiter" button calls `POST /applications` with `candidate_id`, `job_id`, `draft`, and `send_confirmed=True`. Backend invokes `send_email_tool` and returns the message ID.
- Frontend displays: "Email sent to [recruiter] at [timestamp]. Message ID: [xxx]."

**Phase 6 check**: Real email received in the test inbox with the drafted subject and body. Manual: click Send, check inbox within 30s. `AuditLogEntry` shows `status="sent"` with the message ID. Failure path: temporarily set `ALIYUN_SMTP_PASS=wrong`, click Send, confirm the audit log shows `status="failed"` and the frontend shows an error toast.

### Phase 7: Deployment to Alibaba Cloud Function Compute (Day 20-22)

**7.1 Single-container packaging**
- `deploy/Dockerfile` — Python 3.11 slim, installs `backend/requirements.txt` and `frontend/requirements.txt`, copies both apps, runs nginx in the foreground reverse-proxying `/api/*` to `uvicorn :9000` and `/` to `streamlit :8501`. Single image, single deployable unit — fewer moving parts than two containers.
- `deploy/nginx.conf` — included in the image.

**7.2 Push to Alibaba Container Registry (ACR)**
- Create a personal ACR instance in Singapore. Tag and push the image.

**7.3 Deploy to Function Compute with custom container runtime**
- HTTP trigger on port 9000 (the nginx port).
- Environment variables from the secrets file: `QWEN_API_KEY`, `QWEN_BASE_URL`, `ALIYUN_SMTP_USER`, `ALIYUN_SMTP_PASS`, `DEPLOY_REGION=sg`.
- Front it with API Gateway for public HTTPS, custom domain optional.

**7.4 Initialize the database on first deploy**
- `db.init_db()` runs on FastAPI startup. If the seeded jobs are missing, `seed_from_json()` is called. Container restart resets SQLite — accept this for the demo (judges won't be testing at scale). An `/admin/reseed` endpoint is exposed for manual reset.

**Phase 7 check**: Visit the public URL from a fresh browser session. Complete the full flow. `GET /api/jobs` returns the 30+ seed jobs. Audit log shows the deploy instance's events.

### Phase 8: Documentation & Submission Package (Day 23-26)

**8.1 Architecture diagram**
- `docs/architecture.png` — Mermaid source in `docs/architecture.mmd`, rendered to PNG. Must show: candidate browser → Streamlit (8501) → nginx → FastAPI (9000) → Qwen-Agent → Qwen3-VL-Plus (parse) + qwen3-max (match + reasoning) + Qwen-Agent (orchestrator) → DirectMail (send). All on Alibaba Cloud Singapore.

**8.2 `README.md` at repo root**
- One-page overview, screenshots, quickstart, architecture link, track rationale, judging-criteria coverage, deployment instructions, license.

**8.3 Demo video — 3 minutes max**
- Script: (0:00-0:30) hook + problem statement; (0:30-1:00) upload CV; (1:00-1:30) match results appear in sidebar; (1:30-2:00) screening Q&A in chat; (2:00-2:30) email preview renders; (2:30-2:50) email sent, recruiter inbox visible; (2:50-3:00) wrap + tech stack callout. Upload to YouTube (unlisted) or Vimeo; link in the Devpost form.

**8.4 Devpost submission**
- Title, **Track 4** selection, description, repo URL, demo video URL, architecture diagram URL.
- **Proof of Alibaba Cloud deployment**: include a direct link to a code file that imports an Alibaba Cloud service. The cleanest pick is `backend/services/email.py` — the `import smtplib` plus the `smtpdm.aliyun.com` host string is the literal evidence. The rules require "a link to a code file in their code repo that demonstrates use of Alibaba Cloud services and APIs."

**8.5 (Optional) Blog post for the Blog Post Prize**
- Medium / dev.to / Hashnode. Walk through one end-to-end flow with screenshots. Call out the Qwen API choices and the MCP tool design.

**Phase 8 check**: All Devpost form fields complete; all URLs resolve; the demo video plays in the first 3 minutes without audio cuts; the Alibaba-Cloud-evidence file is linked from the submission text.

## Critical files & anchors

- `backend/agent/orchestrator.py` — Qwen-Agent setup, system prompt, tool-attachment order. The system prompt and tool list here determine agent behavior end-to-end. Re-read before any agent-behavior change.
- `backend/agent/matching.py` — `match_score` algorithm. The composite formula, tier thresholds, and `ADJACENT_SKILLS` dict are the project's intellectual core. Re-read before tuning match quality.
- `backend/services/resume_parser.py` — Qwen3-VL-Plus call. The system prompt and base64-handling code determine parse quality on messy PDFs. Re-read before changing parse behavior.
- `backend/app.py` — FastAPI endpoints and audit-log wiring. The `send_confirmed` enforcement in `/applications` is the human-in-the-loop guarantee. Re-read before touching the send path.
- `frontend/streamlit_app.py` — Chat loop, session state, the "Send to Recruiter" button. The single path to `send_email_tool` lives here; the human-in-the-loop guarantee is enforced on both sides (this file sets the flag, `app.py` checks it).

## Verification

**End-to-end smoke test (must pass on the deployed URL before submission)**:

1. Open the deployed URL in a fresh browser session.
2. Upload `data/test_resumes/sample_fullstack.pdf`. Assert: chat replies within 5s with a parsed summary; sidebar shows ≥1 match.
3. Type "show me the matches". Assert: top-5 jobs appear in the sidebar with scores and reasoning snippets.
4. Type "yes, apply to the top one". Assert: agent asks 2–3 screening questions.
5. Answer each with a one-sentence reply. Assert: agent returns a draft email in the Email Preview tab.
6. Click "Send to Recruiter". Assert: success toast within 10s, audit log shows `status="sent"` with a message ID, and the recruiter inbox shows the email.
7. **Failure path** — upload a corrupted PDF. Assert: error message in chat, no application created.
8. **Ambiguous input** — upload a CV with no clear job title. Assert: agent asks clarifying questions before attempting to match.
9. **HITL enforcement** — manually call `POST /applications` with `send_confirmed=False`. Assert: 403, no email sent, audit log shows the attempt was rejected.

**Tests that must pass locally**:
- `pytest tests/test_resume_parser.py -v` — 5/5
- `pytest tests/test_matching.py -v` — 12/12
- `pytest tests/test_agent_flow.py -v` — full simulated conversation with mocked LLM
- `pytest tests/test_jobs_crud.py -v` — CRUD against SQLite

**Manual checks against judging criteria**:
- **Innovation (30%)**: `grep -c "def " backend/agent/tools.py` shows 6 tool functions; `grep -r "qwen3-vl-plus\|qwen3-max" backend/` shows usage in at least 3 files; `wc -l backend/agent/aliases.py backend/agent/matching.py` shows non-trivial size.
- **Technical (30%)**: confirm `backend/{agent,services,models,db.py,app.py}` structure; `grep -A2 "try:" backend/services/email.py` shows retry logic; `grep "AuditLogEntry" backend/app.py` shows audit logging on every endpoint.
- **Problem Value (25%)**: confirm the README articulates the recruiting-company pain point (cost of manual screening at scale); confirm the demo video shows a real end-to-end flow with a real received email.
- **Presentation (15%)**: confirm `docs/architecture.png` exists and shows the full pipeline; confirm the demo video is ≤3 min; confirm the README has ≥2 screenshots.

## Assumptions & contingencies

- **Region**: Singapore for Qwen Cloud and Alibaba Cloud. If the demo presenter is in a region with high Singapore latency, switch Function Compute to Hong Kong or US-Virginia — the Qwen Cloud base URL is region-specific; `backend/config.py` reads `QWEN_BASE_URL` from env, so this is a one-line config change, no code change.
- **Database**: SQLite is sufficient for the demo and saves cost. If judges test concurrency or persistence across container restarts, switch to ApsaraDB RDS for PostgreSQL — the SQLAlchemy code is portable, only the connection string changes.
- **LLM cost**: the $40 voucher is generous for the build period. Cache `qwen3-max` reasoning scores in `data/recruiter.db` keyed by `(candidate_id, job_id)` — re-parsing the same CV must not re-call VL or the reasoning model. The cache check is in `parse_resume` and `match_score`.
- **DirectMail sender verification**: must be done before Phase 7 deploy. Fallback if DirectMail setup fails: use `smtp.gmail.com` with an app password for the demo — works for testing, but disqualifies the "deployed on Alibaba Cloud" claim for email specifically. Keep all other Alibaba Cloud services (FC, ACR, API Gateway) as the proof of deployment.
- **Qwen3-VL-Plus availability**: confirmed at planning time. If the model id changes between now and Phase 2, the constant in `backend/config.py` is the single point of update.
- **Build window**: 4 weeks of focused build time fits the 7 phases if execution starts on registration day (May 26, 2026). If a phase slips, drop Phase 8.5 (the blog post) — the Blog Post Prize is optional, the Track 4 grand prize is not.
- **Human-in-the-loop guarantee**: enforced on both sides — the agent's system prompt forbids `send_email_tool` without prior click, AND the FastAPI `/applications` endpoint checks `send_confirmed`. Defense in depth: the LLM-level guard prevents accidental sends in normal flow; the API-level guard prevents any abuse path.

<!-- BEGIN:frontend-conventions -->
# Frontend: React + TypeScript + Vite + MUI v9

This project uses **MUI v9** — the API differs from MUI v5/v6 in training data. Before touching any component, note these breaking changes:

## MUI v9 breaking changes
- **Grid**: `item` prop is removed. Use `size={{ xs: 12, md: 8 }}` instead of `item xs={12} md={8}`.
- **Typography**: `fontWeight` and `display` are no longer direct props. Use `sx={{ fontWeight: 'medium' }}` and `sx={{ display: 'block' }}`.
- **ListItemText**: `primaryTypographyProps` is removed. Use `slotProps={{ primary: { variant: 'body2' } }}`.

## TypeScript strictness
- `verbatimModuleSyntax` is enabled in `tsconfig.app.json` — all type-only imports MUST use `import type { Foo }`.
- `noUnusedLocals` and `noUnusedParameters` are enabled — no dead code tolerated.
- Oxlint enforces `rules-of-hooks` (error) and `only-export-components` (warn).

## API client
- All functions in `src/api/client.ts` return **unwrapped data** (not `AxiosResponse`). They chain `.then(r => r.data)`.
- When adding a new endpoint, add the same `.then(r => r.data)` + explicit return type annotation.
- API base URL: `VITE_API_URL` env var, default `http://localhost:9000`.

## React Query hooks
- `src/api/hooks.ts` defines a helper: `type QueryOpts<T> = Omit<UseQueryOptions<T, Error>, 'queryKey' | 'queryFn'>`.
- All hook option parameters use `QueryOpts<T>`, NOT raw `UseQueryOptions`.
- Mutations use `mutateAsync` — callers are `async/await`, not callbacks.

## State management
- **Zustand** (`src/store/index.ts`) for client state (candidateId, chat history, cache).
- **TanStack React Query** for server state (candidates, jobs, matches, audit log).
- Never duplicate server state into Zustand — use React Query cache.

## Build & lint
```bash
npm run lint     # oxlint — must pass with 0 diagnostics
npm run build    # tsc -b && vite build — must compile clean
npm run dev      # Vite dev server with HMR
```
<!-- END:frontend-conventions -->

<!-- BEGIN:backend-conventions -->
# Backend: FastAPI + SQLAlchemy + SQLite

## Project architecture
The backend follows a **ports-and-adapters** pattern:
- `backend/domain/` — entities, value objects, domain services
- `backend/application/` — use cases, ports (interfaces), application services
- `backend/infrastructure/` — gRPC server, WebSocket, orchestration (LangGraph), adapters
- `backend/services/` — business logic (resume parser, email, CRUD)

## API endpoints (REST — implemented in `backend/app.py`)
- `GET  /status` — service config status (api_key_configured, smtp_configured, version)
- `POST /upload` — upload CV PDF (multipart/form-data), returns candidate_id + parsed data
- `GET  /jobs` — list all jobs
- `GET  /jobs/{job_id}` — get single job
- `POST /applications` — submit application; **email only sends if `send_confirmed=true`**
- `GET  /audit-log` — audit trail (query: limit, candidate_id)
- `POST /admin/reseed` — re-seed jobs from JSON

⚠️ **Frontend-backend mismatch**: The React frontend calls `POST /chat`, `POST /match`, and `GET /candidates/{id}` but these endpoints do NOT exist in `app.py`. The `/chat` endpoint was replaced by gRPC (`backend/infrastructure/grpc/`). Before the app works end-to-end, either add REST wrappers for these or update the frontend to use gRPC-Web.

## Human-in-the-loop guarantee
The email send is gated at **two levels**:
1. **API**: `/applications` returns `{"status": "draft_saved"}` when `send_confirmed=False` — email is never sent.
2. **Frontend**: UI previews the draft; the "Send" button explicitly sets `send_confirmed=True`.

Never bypass either gate. Never infer `send_confirmed` from context.

## Database
- **SQLite** at `data/recruiter.db` (gitignored).
- Use `get_session()` context manager — auto-commits on success, rolls back on error.
- Seed data: `data/seed_jobs.json` — 32 realistic job listings.
- Models: `Candidate`, `Job`, `Application`, `AuditLog`, `ParsedResume`.
- All models have a `to_dict()` method for JSON serialization.

## AI models
- **Resume parsing**: `qwen3-vl-plus` (vision model)
- **Matching reasoning**: `qwen3-max`
- **Screening questions**: `qwen3-max`
- **Email drafting**: `qwen3-max`
- Base URL: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`

## Email
- **Alibaba DirectMail SMTP** — configured via `ALIYUN_SMTP_USER`, `ALIYUN_SMTP_PASS`, `SMTP_SENDER`.
- `send_email()` in `backend/services/email.py` raises `EmailSendError` on failure.
- Always log to audit trail after send (success or failure).
<!-- END:backend-conventions -->

<!-- BEGIN:environment-config -->
# Environment & Config

Copy `.env.example` to `.env` and configure:

| Variable | Required | Default | Notes |
|---|---|---|---|
| `QWEN_API_KEY` | Yes | — | Qwen Cloud API key |
| `QWEN_BASE_URL` | No | dashscope-intl.aliyuncs.com | |
| `MODEL_REASONING` | No | `qwen3-max` | For matching + screening |
| `MODEL_VISION` | No | `qwen3-vl-plus` | For CV parsing |
| `ALIYUN_SMTP_USER` | For email | — | DirectMail SMTP |
| `ALIYUN_SMTP_PASS` | For email | — | DirectMail password |
| `SMTP_SENDER` | For email | — | Sender address |
| `API_HOST` | No | `0.0.0.0` | |
| `API_PORT` | No | `9000` | |

The **frontend** uses `VITE_API_URL` (default `http://localhost:9000`).
<!-- END:environment-config -->

<!-- BEGIN:deployment-conventions -->
# Deployment

## Docker (multi-stage)
```bash
docker build -t talentpilot -f deploy/Dockerfile .
docker run -p 9000:9000 -e QWEN_API_KEY="..." talentpilot
```
- **Stage 1**: `node:22-alpine` builds `frontend-react/` → `dist/`
- **Stage 2**: `python:3.11-slim` runs uvicorn (port 8000) + nginx (port 9000)
- Nginx serves `/` from `dist/` (SPA fallback to `index.html`), proxies `/api/` to uvicorn.

## Local development
```bash
# Backend
uvicorn backend.app:app --reload --port 9000

# Frontend (separate terminal)
cd frontend-react && npm run dev
```

## Before pushing
- `cd frontend-react && npm run lint && npm run build` — must pass
- `pytest tests/ -v` — backend tests must pass
- Environment variables must NOT be committed (`.env` is gitignored)
<!-- END:deployment-conventions -->

<!-- BEGIN:commit-conventions -->
# Commit Conventions

## Commit incrementally, not in bulk
- Commit after each logical unit of work is complete and verified (compiles, tests pass).
- Never accumulate 10+ files across unrelated concerns before committing.
- A commit message should describe ONE thing: a fix, a feature, a refactor — not a laundry list.
- If a change spans multiple independent fixes, split them into separate commits.
- Rule of thumb: if the commit message needs "and" more than twice, it should be two commits.

## Frontend-specific
- A component change + its test → one commit.
- Adding a new API hook → one commit for the hook, one for the component that uses it.
- CSS/style changes → separate from logic changes.
<!-- END:commit-conventions -->

<!-- BEGIN:file-organization -->
# File Organization

Never create new files when an existing file is the natural home:
- New React components → `frontend-react/src/components/`
- New API calls → `frontend-react/src/api/client.ts` (function) + `hooks.ts` (hook)
- New backend endpoints → `backend/app.py` (for simple handlers) or a new module in `backend/infrastructure/`
- New domain logic → `backend/domain/` or `backend/services/`
- New infrastructure → `backend/infrastructure/`

## Don't pollute the root
- Config files belong in their respective directories (e.g., `frontend-react/tsconfig.json`, not root).
- Documentation lives in `docs/` or as `*.md` in the relevant subdirectory.
- Scripts live in `deploy/`.
<!-- END:file-organization -->

<!-- BEGIN:code-review-checklist -->
# Code Review Checklist

## Every PR must
- [ ] `npm run lint` passes (0 diagnostics) in `frontend-react/`
- [ ] `npm run build` passes (tsc + vite) in `frontend-react/`
- [ ] `pytest tests/ -v` passes in root
- [ ] No unused imports or variables (TypeScript `noUnusedLocals`/`noUnusedParameters` enforced)
- [ ] New API endpoints have audit logging (`log_audit`)
- [ ] Email-sending paths enforce `send_confirmed=True` gating
- [ ] MUI v9 components use the v9 API (no `fontWeight` prop, no `item` on Grid, no `primaryTypographyProps`)
- [ ] Type-only imports use `import type` syntax
- [ ] API client functions return unwrapped data (`.then(r => r.data)`)
- [ ] Environment variables referenced in code are documented in `.env.example`
<!-- END:code-review-checklist -->

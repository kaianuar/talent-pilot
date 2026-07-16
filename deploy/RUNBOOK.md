# Deployment runbook — Alibaba Cloud

This is the step-by-step procedure for putting TalentPilot on Alibaba Cloud
so the demo video can be recorded against a live URL.

The application is one container that runs:
- **nginx** on port 9000 (serves the React SPA + proxies /upload, /match, etc. to FastAPI)
- **FastAPI** (uvicorn) on port 8000 (internal only — not exposed)

The container is pushed to Alibaba Container Registry (ACR), then run via
one of two options:
- **Option A: Function Compute with custom container** — cheapest, ~30 min setup
- **Option B: ECS with Docker** — fastest, ~10 min if you have an ECS instance

## Prerequisites

- Alibaba Cloud account with billing enabled
- `aliyun` CLI installed locally OR a working browser
- Docker Desktop installed locally (already done)
- A Qwen Cloud API key (`QWEN_API_KEY`)
- An Alibaba DirectMail SMTP user/pass for the email send feature
  (optional for the demo if you don't trigger /applications)

---

## Option A: Function Compute (recommended)

### Step 1 — Create ACR namespace and repo

Console: Container Registry (容器镜像服务) → Personal Edition → Create Namespace
- Namespace: `talentpilot` (must be globally unique; pick a unique one if collision)
- Default access: Public (so the function can pull without extra auth)

Then in that namespace, create a repository:
- Region: same as your Function Compute region
- Repository name: `talentpilot`
- Visibility: Private (we'll set a pull policy in FC anyway)

### Step 2 — Build and push the image

From the repo root:

```bash
# Login to ACR
ACR_REGISTRY="registry.<region>.cr.aliyuncs.com"   # e.g. registry.ap-southeast-1.cr.aliyuncs.com
ACR_USER="<your aliyun account>"
ACR_PASS=$(aliyun cr get-authorization-token --region <region> | python3 -c "import sys,json; print(json.load(sys.stdin)['authorizationToken'])")

echo "$ACR_PASS" | docker login --username "$ACR_USER" --password-stdin "$ACR_REGISTRY"

# Build and push
docker build -t talentpilot:latest -f deploy/Dockerfile .
docker tag talentpilot:latest "$ACR_REGISTRY/talentpilot/talentpilot:latest"
docker push "$ACR_REGISTRY/talentpilot/talentpilot:latest"
```

(If `aliyun` CLI is too painful, get the temporary password from the console:
ACR → namespace → Access Credentials → Temporary Password.)

### Step 3 — Create Function Compute

Console: Function Compute (函数计算) → Create Function

- Runtime: **Custom Container**
- Region: same as ACR
- Image: select from ACR → `talentpilot/talentpilot:latest`
- Container port: **9000**
- Memory: 2048 MB (LangGraph + LLM calls need headroom; 1024 works for the demo)
- Timeout: 300 seconds (cold-start + first LLM call)
- Instance concurrency: 1 (avoid SQLite write conflicts; demo is single-user)

### Step 4 — Configure environment variables

In the FC function → Configuration → Environment Variables, set:

| Key | Value |
|---|---|
| `QWEN_API_KEY` | your Qwen API key |
| `QWEN_BASE_URL` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| `MODEL_REASONING` | `qwen3-max` |
| `MODEL_VISION` | `qwen3-vl-plus` |
| `MODEL_CHAT` | `qwen-turbo` |
| `ALIYUN_SMTP_USER` | your DirectMail user |
| `ALIYUN_SMTP_PASS` | your DirectMail password |
| `SMTP_SENDER` | your verified sender address |
| `API_HOST` | `0.0.0.0` |
| `API_PORT` | `8000` |

`VITE_API_URL` is **baked in at build time** by the Dockerfile. The current
build leaves it empty, so the React app calls the API on the same origin
(it works because the React SPA and the API are both served from the
function's URL).

### Step 5 — Create HTTP trigger

In the function, add a trigger:
- Type: HTTP Trigger
- Auth: Allow anonymous (for the public demo)
- Methods: GET, POST, OPTIONS, PUT, DELETE (any)

The trigger gives you a URL like `https://talentpilot-xxx.region.fcapp.run`.

### Step 6 — Smoke test

From your local machine:

```bash
./deploy/smoke-test.sh https://talentpilot-xxx.region.fcapp.run
```

All six checks should pass. If they don't, jump to **Troubleshooting** below.

---

## Option B: ECS with Docker (fastest if you already have an ECS)

### Step 1 — SSH in and install Docker

```bash
ssh root@<your-ecs-ip>
curl -fsSL https://get.docker.com | sh
```

### Step 2 — Pull the image

```bash
docker pull registry.<region>.cr.aliyuncs.com/talentpilot/talentpilot:latest
```

### Step 3 — Run the container

```bash
docker run -d \
  --name talentpilot \
  --restart unless-stopped \
  -p 9000:9000 \
  -e QWEN_API_KEY="<your-key>" \
  -e QWEN_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1" \
  -e MODEL_REASONING=qwen3-max \
  -e MODEL_VISION=qwen3-vl-plus \
  -e MODEL_CHAT=qwen-turbo \
  -e ALIYUN_SMTP_USER="<smtp-user>" \
  -e ALIYUN_SMTP_PASS="<smtp-pass>" \
  -e SMTP_SENDER="noreply@yourdomain.com" \
  registry.<region>.cr.aliyuncs.com/talentpilot/talentpilot:latest
```

### Step 4 — Open the security group

ECS console → Security Groups → Add inbound rule: TCP 9000 from 0.0.0.0/0
(or your IP for tighter security).

### Step 5 — Smoke test

```bash
./deploy/smoke-test.sh http://<your-ecs-ip>:9000
```

---

## Troubleshooting

### `curl: (7) Failed to connect to ...`

- Function Compute: the trigger URL might be HTTPS-only. Add `-k` to curl to skip cert verification, or use a real browser.
- ECS: check the security group. The default Aliyun ECS security group blocks port 9000.

### `/jobs` returns 0 jobs

The container should auto-seed the SQLite DB with `data/seed_jobs.json` on
first run. If it returns 0, the DB file isn't writable. Check the container
logs:

```bash
# Function Compute
aliyun fc logs --service-name <svc> --function-name <fn> --region <region> --since 1h

# ECS
docker logs talentpilot
```

Look for `seed_from_json` output.

### CORS errors in the browser console

The backend already has `allow_origins=["*"]` in `CORSMiddleware`. If the
browser still complains, check the request was actually reaching the
backend (network tab) and not nginx (which would return a 404 in static).

### First /upload takes 30+ seconds

The first resume parse call to qwen3-vl-plus (or qwen-turbo) plus the
matching call to qwen3-max will cold-start. Subsequent calls are <2s.
Function Compute cold-start adds another 3-5s. Not a bug.

### Email send fails with 5xx

`/applications` will return 500 if DirectMail rejects the request.
Check `SMTP_SENDER` is verified in the DirectMail console, and the
`ALIYUN_SMTP_USER`/`PASS` are correct. The audit log will have the
error message.

### 502 from Function Compute

The function timed out (default 60s). Bump the timeout in the FC config
to 300s for the first cold start.

### Container keeps restarting on ECS

`docker logs talentpilot` will show why. Common: `QWEN_API_KEY` not set
(import error on startup), or `data/` directory not writable.

---

## Production URL checklist (for Devpost)

- [ ] Function Compute / ECS is running
- [ ] `./deploy/smoke-test.sh <url>` returns all 6 checks pass
- [ ] Browser can load the React SPA at `/`
- [ ] Browser can upload a PDF and see parsed fields
- [ ] Browser can click `/match` and see job cards
- [ ] Browser can start a screening session and answer one question
- [ ] (Optional) Browser can submit an application and see the audit log entry

The exact URL you use is what goes in the Devpost "Proof of deployment" field.

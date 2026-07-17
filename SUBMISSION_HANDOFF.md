# Submission handoff

Everything in this repo is in a submission-ready state. The local
Docker container was built and end-to-end verified against the real
Qwen API. What remains is **actions only you can take** (cloud
credentials, GitHub repo creation, demo recording).

This file is a checklist with copy-pasteable commands.

---

## 1. Push the GitHub repo (5 min)

The repo has no remote yet. Pick a name and create it on GitHub:

1. Go to https://github.com/new
2. Repository name: `talentpilot` (or your preference)
3. Visibility: **Public** (Devpost requires this)
4. **DO NOT** initialize with README, .gitignore, or license — they're already in the repo
5. Click "Create repository"

Then locally, push the existing repo:

```bash
cd ~/qwen-hackathon
git remote add origin https://github.com/<your-username>/talentpilot.git
git push -u origin main
```

If you want a tag for the submission:

```bash
git tag -a v1.0.0 -m "Devpost submission: TalentPilot"
git push origin v1.0.0
```

**The URL `https://github.com/<your-username>/talentpilot` goes in
the Devpost "Source code" field.**

---

## 2. Deploy to Alibaba Cloud (30-60 min)

The Docker image `talentpilot:test` is built and works. Two paths:

### Option A: Function Compute (cheapest, ~30 min)

Follow `deploy/RUNBOOK.md` Option A. Short version:

```bash
# Login to ACR
ACR_REGISTRY="registry.<region>.cr.aliyuncs.com"   # e.g. ap-southeast-1
ACR_USER="<your aliyun account>"
ACR_PASS=$(aliyun cr get-authorization-token --region <region> \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['authorizationToken'])")
echo "$ACR_PASS" | docker login --username "$ACR_USER" --password-stdin "$ACR_REGISTRY"

# Tag and push
docker tag talentpilot:test "$ACR_REGISTRY/talentpilot/talentpilot:latest"
docker push "$ACR_REGISTRY/talentpilot/talentpilot:latest"
```

Then in the Function Compute console:
- Create function with "Custom Container" runtime
- Image URI: `$ACR_REGISTRY/talentpilot/talentpilot:latest`
- Container port: **9000**
- Memory: 2048 MB
- Timeout: 300s
- Set the env vars from `.env.example` (paste your real values)
- Add an HTTP trigger, allow anonymous

### Option B: ECS with Docker (fastest if you have one)

```bash
ssh root@<your-ecs-ip>
docker pull <your-acr-registry>/talentpilot/talentpilot:latest

docker run -d \
  --name talentpilot \
  --restart unless-stopped \
  -p 9000:9000 \
  -e QWEN_API_KEY="$(cat ~/.qwen_key)" \
  -e QWEN_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1" \
  -e MODEL_REASONING=qwen3-max \
  -e MODEL_VISION=qwen3-vl-plus \
  -e MODEL_CHAT=qwen-turbo \
  -e ALIYUN_SMTP_USER="<your-smtp-user>" \
  -e ALIYUN_SMTP_PASS="<your-smtp-pass>" \
  -e SMTP_SENDER="<your-sender>" \
  <your-acr-registry>/talentpilot/talentpilot:latest
```

Then open port 9000 in the ECS security group.

---

## 3. Verify the deployment

```bash
cd ~/qwen-hackathon
./deploy/smoke-test.sh https://<your-cloud-url>
```

All 6 checks should pass. If they don't, see `deploy/RUNBOOK.md`
"Troubleshooting".

---

## 4. Record the demo video (~3 min)

Follow `docs/DEMO_VIDEO_SCRIPT.md`. Key points:

- **Use the cloud URL, not localhost.** Judges want to see the deployed app.
- **Pre-warm before recording.** First /upload takes 5-10s (cold start
  + LLM parse). Do a full dry run 60s before pressing record.
- **Open Chrome dev tools Network tab** on the right side. Showing real
  LLM calls in flight proves the AI is real.
- **Use a real PDF.** Fake-looking resumes look fake.

Upload to YouTube (unlisted is fine) or Vimeo. The video URL goes in
the Devpost "Demo video" field.

---

## 5. Fill in the Devpost form

Required fields:

| Field | Value |
|---|---|
| Project name | TalentPilot |
| Tagline | "From CV to recruiter email, with the candidate in control" |
| Track | **Track 4: Autopilot Agent** |
| Source code URL | `https://github.com/<user>/talentpilot` |
| Demo video URL | your YouTube/Vimeo URL |
| Proof of Alibaba Cloud | The URL of the deployed app, plus a link to `backend/services/email.py` (the DirectMail import is the literal evidence of Alibaba Cloud service use) |
| Description | ~300 words covering problem, approach, architecture (see below) |
| Architecture diagram | `docs/architecture.mmd` (render to PNG) |

**Description skeleton (fill in your own words):**

> TalentPilot is an AI recruiter agent that takes a candidate from CV
> upload to a recruiter-ready email in one autonomous flow.
>
> The candidate uploads a PDF. qwen-turbo parses text-extractable
> resumes; qwen3-vl-plus handles scanned ones. The parsed profile
> scores against 32 seeded jobs using a weighted formula (skill
> coverage 35%, adjacent-skill bonus 20%, experience 20%, LLM
> reasoning 25%). The reasoning scores are cached on
> (candidate, job, resume-hash) so re-runs are deterministic.
>
> The candidate picks a top match and starts a screening session
> driven by a LangGraph state machine. qwen3-max reads the resume,
> identifies skill gaps, and asks a targeted question. The
> candidate answers; the same model assesses quality. The session
> ends with a drafted recruiter email and a human-in-the-loop
> gate.
>
> **No email leaves the system until the candidate confirms.** The
> gate is enforced at two layers: the API returns 403 unless
> `send_confirmed=True`, and the frontend's "Send to Recruiter"
> button is the only path that sets that flag.
>
> Architecture: hexagonal (domain / application / infrastructure),
> gRPC streaming for real-time questions, WebSocket for progress,
> REST for everything else, React + TypeScript + MUI v9 frontend.

---

## What's already done

- 283/283 backend tests pass, 128/128 frontend tests pass
- 8 commits in this session fixing bugs and adding the deploy artifacts
- Docker image builds cleanly (391 MB)
- End-to-end verified live in Docker: upload → parse → match → screening,
  with the real Qwen API
- 4 production bugs caught and fixed during live testing:
  - experience_score divisor (`/10.0` → `/min_years`)
  - LLM reasoning non-determinism (cache)
  - nginx path mismatches
  - `.env` quoted API key

The only remaining work is the **cloud push and demo recording**,
which require your Alibaba Cloud credentials and your voice.

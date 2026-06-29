# Deployment Guide

## Quick Start (Local)

```bash
# Install backend dependencies
pip install -r backend/requirements.txt

# Build React frontend
cd frontend-react && npm install && npm run build && cd ..

# Set environment variables
export QWEN_API_KEY="your-api-key-here"

# Start the backend
uvicorn backend.app:app --reload --port 9000 &
```

Open http://localhost:9000 in your browser.

For frontend development with hot-reload, run `cd frontend-react && npm run dev` separately.

## Docker Deployment

```bash
# Build
docker build -t talentpilot -f deploy/Dockerfile .

# Run
docker run -p 9000:9000 \
  -e QWEN_API_KEY="your-key" \
  -e ALIYUN_SMTP_USER="your-smtp-user" \
  -e ALIYUN_SMTP_PASS="your-smtp-pass" \
  talentpilot
```

## Alibaba Cloud Function Compute

1. Push image to ACR using `deploy/deploy.sh`
2. Create Function Compute function with custom container runtime
3. Configure environment variables
4. Create HTTP trigger

See `deploy/deploy.sh` for detailed steps.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `QWEN_API_KEY` | Yes | Qwen Cloud API key |
| `QWEN_BASE_URL` | No | DashScope endpoint (default: Singapore) |
| `MODEL_REASONING` | No | Model for matching (default: qwen3-max) |
| `MODEL_VISION` | No | Model for CV parsing (default: qwen3-vl-plus) |
| `ALIYUN_SMTP_USER` | For email | DirectMail SMTP username |
| `ALIYUN_SMTP_PASS` | For email | DirectMail SMTP password |
| `SMTP_SENDER` | For email | Sender email address |

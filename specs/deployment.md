# Deployment Spec

## Target Platform
**Alibaba Cloud Function Compute** (Singapore Region) with custom container runtime.

## Container Architecture

Single container running three processes behind nginx:

```
┌─────────────────────────────────────┐
│         Docker Container            │
│                                     │
│  ┌─────────┐  ┌─────────┐  ┌─────┐│
│  │ Uvicorn │  │Streamlit│  │Nginx ││
│  │ (8000)  │  │ (8501)  │  │(9000)││
│  └────┬────┘  └────┬────┘  └──┬───┘│
│       │            │          │    │
│       └────────────┼──────────┘    │
│                    │               │
│              ┌─────▼─────┐        │
│              │  SQLite DB │        │
│              │ (data/)    │        │
│              └───────────┘        │
└─────────────────────────────────────┘
```

## Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt frontend/requirements.txt ./
RUN pip install --no-cache-dir -r backend/requirements.txt -r frontend/requirements.txt

# App code
COPY backend/ frontend/ data/ ./
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/start.sh ./
RUN chmod +x start.sh

EXPOSE 9000
CMD ["./start.sh"]
```

## Nginx Configuration

```nginx
server {
    listen 9000;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;  # FastAPI
    }

    location / {
        proxy_pass http://127.0.0.1:8501;   # Streamlit
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Startup Script (start.sh)

1. Start `uvicorn backend.app:app --host 0.0.0.0 --port 8000` in background
2. Start `streamlit run frontend/streamlit_app.py --server.port 8501` in background
3. Start `nginx -g "daemon off;"` in foreground
4. Trap SIGTERM/SIGINT for graceful shutdown

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `QWEN_API_KEY` | Yes | Qwen Cloud API key |
| `QWEN_BASE_URL` | No | DashScope endpoint (default: Singapore) |
| `MODEL_REASONING` | No | Model ID (default: qwen3-max) |
| `MODEL_VISION` | No | Model ID (default: qwen3-vl-plus) |
| `ALIYUN_SMTP_USER` | For email | DirectMail SMTP username |
| `ALIYUN_SMTP_PASS` | For email | DirectMail SMTP password |
| `SMTP_SENDER` | For email | Sender email address |
| `DEPLOY_REGION` | No | Region code (default: sg) |

## Deployment Steps

### 1. Build Image
```bash
docker build -t talentpilot -f deploy/Dockerfile .
```

### 2. Push to ACR
```bash
# Tag
docker tag talentpilot registry.sg.cr.aliyuncs.com/namespace/talentpilot:latest

# Login to ACR
docker login registry.sg.cr.aliyuncs.com

# Push
docker push registry.sg.cr.aliyuncs.com/namespace/talentpilot:latest
```

### 3. Create Function Compute Function
- Runtime: Custom Container
- Image: ACR image URI
- Port: 9000
- Memory: 2GB (for LLM client libraries)
- Timeout: 300s

### 4. Configure HTTP Trigger
- Authentication: None (public)
- Method: GET, POST

### 5. Set Environment Variables
- Add all required env vars in Function Compute console

### 6. Test
```bash
# Health check
curl https://your-function-url/jobs

# Full flow
# Open in browser and complete CV upload → match → screen → email
```

## Database Initialization

On FastAPI startup:
1. `init_db()` creates tables if they don't exist
2. `seed_from_json()` loads seed jobs if table is empty
3. Container restart resets SQLite (acceptable for demo)

Manual reset: `POST /admin/reseed`

## Local Development

```bash
# Terminal 1: Backend
uvicorn backend.app:app --reload --port 9000

# Terminal 2: Frontend
streamlit run frontend/streamlit_app.py --server.port 8501
```

Or use Docker locally:
```bash
docker build -t talentpilot -f deploy/Dockerfile .
docker run -p 9000:9000 -e QWEN_API_KEY="your-key" talentpilot
```

## Cost Estimate

| Service | Free Tier | Estimated Cost |
|---------|-----------|----------------|
| Function Compute | 1M invocations + 400K CU-s/month (3 months) | $0 |
| ACR | 500MB storage | $0 |
| DirectMail | 200 emails/day | $0 |
| Qwen Cloud | $40 voucher | $0 |
| **Total** | | **$0** (within free tier + voucher) |

## Proof of Deployment

For Devpost submission, include:
1. Link to `backend/services/email.py` (shows `smtpdm.aliyun.com` usage)
2. Separate recording of the deployed URL working
3. Architecture diagram showing Alibaba Cloud components

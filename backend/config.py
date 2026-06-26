"""Application configuration. Reads from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Auto-load .env file from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "recruiter.db"
SEED_JOBS_PATH = DATA_DIR / "seed_jobs.json"
UPLOADS_DIR = DATA_DIR / "uploads"

# Qwen Cloud (DashScope International)
QWEN_API_KEY = os.environ.get("QWEN_API_KEY", "")
QWEN_BASE_URL = os.environ.get(
    "QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
)

# Model IDs
MODEL_REASONING = os.environ.get("MODEL_REASONING", "qwen3-max")
MODEL_CHAT = os.environ.get("MODEL_CHAT", "qwen-turbo")
MODEL_VISION = os.environ.get("MODEL_VISION", "qwen3-vl-plus")

# Alibaba DirectMail SMTP
SMTP_HOST = os.environ.get("ALIYUN_SMTP_HOST", "smtpdm.aliyun.com")
SMTP_PORT = int(os.environ.get("ALIYUN_SMTP_PORT", "465"))
SMTP_USER = os.environ.get("ALIYUN_SMTP_USER", "")
SMTP_PASS = os.environ.get("ALIYUN_SMTP_PASS", "")
SMTP_SENDER = os.environ.get("SMTP_SENDER", "noreply@talentpilot.demo")

# Server
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "9000"))
DEPLOY_REGION = os.environ.get("DEPLOY_REGION", "sg")

# Matching thresholds
SCORE_STRONG = 0.75
SCORE_PARTIAL = 0.55
SCORE_WEAK = 0.40

# Composite weights
W_REQUIRED = 0.35
W_ADJACENT = 0.20
W_EXPERIENCE = 0.20
W_REASONING = 0.25

"""Test conftest — load .env before any test module imports."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root before any test module evaluates os.environ
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

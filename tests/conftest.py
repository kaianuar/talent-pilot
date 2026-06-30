"""Test conftest — load .env and suppress known library warnings."""

import os
import warnings
from pathlib import Path
from dotenv import load_dotenv

# Suppress PyMuPDF (fitz) SWIG type warnings — library issue, not ours
warnings.filterwarnings("ignore", message=".*builtin type SwigPy.*")
warnings.filterwarnings("ignore", message=".*builtin type swigvarlink.*")

# Load .env from project root before any test module evaluates os.environ
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

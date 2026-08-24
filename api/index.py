"""Vercel Serverless Function Entry Point."""

import sys
from pathlib import Path

# Add workspace directory to python path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import app

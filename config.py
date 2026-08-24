import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

# Load environment variables explicitly with override before Config class definition
load_dotenv(ENV_FILE, override=True)

IS_VERCEL = bool(os.getenv("VERCEL"))


class Config:
    """Application configuration settings."""
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-singing-bowl-export-2026")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    PORT = int(os.getenv("PORT", 5000))
    BASE_DIR = BASE_DIR

    # Storage paths (Use /tmp on Vercel serverless to avoid read-only filesystem crash)
    if IS_VERCEL:
        DATA_DIR = Path("/tmp/data")
        UPLOAD_FOLDER = Path("/tmp/uploads")
    else:
        DATA_DIR = BASE_DIR / "data"
        UPLOAD_FOLDER = BASE_DIR / "uploads"

    BUYERS_CSV = DATA_DIR / "buyers.csv"
    SENT_LOG_CSV = DATA_DIR / "sent_log.csv"

    # Upload configuration
    ALLOWED_EXTENSIONS = {"pdf"}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload size

    # External Lead Search API (Serper)
    LEAD_SEARCH_API_KEY = os.getenv("LEAD_SEARCH_API_KEY", "")
    LEAD_SEARCH_API_URL = os.getenv("LEAD_SEARCH_API_URL", "https://google.serper.dev/search")

    # Hunter.io Email Finder API Configuration
    HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")

    # Gemini AI Configuration
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    _raw_model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    GEMINI_MODEL = "gemini-3.6-flash" if _raw_model == "gemini-2.5-flash" else _raw_model

    # Gmail settings
    GMAIL_USER = os.getenv("GMAIL_USER", "")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

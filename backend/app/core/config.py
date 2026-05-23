import os
import secrets
import logging
import tempfile
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("cyberverse.config")

# Determine environment mode
APP_ENV: str = os.getenv("APP_ENV", "development").lower().strip()
IS_PRODUCTION: bool = APP_ENV == "production"


def _get_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

# =========================================================================
# Server Port Configuration
# =========================================================================
raw_port = os.getenv("PORT")
if not raw_port:
    if IS_PRODUCTION:
        raise ValueError(
            "CRITICAL STARTUP ERROR: PORT environment variable is missing in PRODUCTION mode. "
            "Railway requires a PORT environment variable to bind to."
        )
    else:
        PORT = 8090
else:
    try:
        PORT = int(raw_port)
    except ValueError as e:
        raise ValueError(
            f"CRITICAL STARTUP ERROR: PORT environment variable '{raw_port}' is not a valid integer: {e}"
        )

# =========================================================================
# Cryptographic Settings
# =========================================================================
raw_secret_key = os.getenv("SECRET_KEY")
if not raw_secret_key or raw_secret_key.strip() in (
    "",
    "your-secret-key-here",
    "CYBER_VERSE_GLOWING_NEON_SECRET_2026",
    "REPLACE_ME_IN_PRODUCTION"
):
    if IS_PRODUCTION:
        raise ValueError(
            "CRITICAL SECURITY ERROR: SECRET_KEY environment variable is missing, "
            "empty, or set to an insecure default value in PRODUCTION mode. "
            "You MUST define a strong, unique SECRET_KEY in your system environment."
        )
    else:
        # Generate cryptographically secure fallback values only for development mode
        SECRET_KEY = secrets.token_urlsafe(64)
        logger.warning(
            "SECRET_KEY was missing or insecure in development. "
            "Automatically generated a secure temporary fallback key."
        )
else:
    SECRET_KEY = raw_secret_key.strip()

# =========================================================================
# Database Settings
# =========================================================================

# Support both DATABASE_URL and PG_DATABASE_URL

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or os.getenv("PG_DATABASE_URL")
)

if not DATABASE_URL:
    if IS_PRODUCTION:
        raise ValueError(
            "CRITICAL STARTUP ERROR: DATABASE_URL or PG_DATABASE_URL environment variable is missing in PRODUCTION mode. "
            "Railway PostgreSQL dynamic connection URI is required."
        )
    else:
        DATABASE_URL = "sqlite:///./instance/cyberverse.db"

# =========================================================================
# Redis Configuration
# =========================================================================
raw_redis_url = os.getenv("REDIS_URL")
if not raw_redis_url:
    if IS_PRODUCTION:
        raise ValueError(
            "CRITICAL STARTUP ERROR: REDIS_URL environment variable is missing in PRODUCTION mode. "
            "Railway Redis connection URI is required."
        )
    else:
        REDIS_URL = "redis://localhost:6379/0"
else:
    REDIS_URL = raw_redis_url.strip()

# =========================================================================
# Preferred Provider & API Keys Settings
# =========================================================================
PREFERRED_LLM_PROVIDER = os.getenv("PREFERRED_LLM_PROVIDER", "groq").lower().strip()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# API Keys validation in production mode
if IS_PRODUCTION:
    _provider_key_map = {
        "anthropic": ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
        "openai": ("OPENAI_API_KEY", OPENAI_API_KEY),
        "groq": ("GROQ_API_KEY", GROQ_API_KEY),
    }
    if PREFERRED_LLM_PROVIDER in _provider_key_map:
        _key_name, _key_val = _provider_key_map[PREFERRED_LLM_PROVIDER]
        if not _key_val:
            raise ValueError(
                f"CRITICAL SECURITY ERROR: {_key_name} is missing in PRODUCTION mode "
                f"with preferred provider '{PREFERRED_LLM_PROVIDER}'."
            )

# =========================================================================
# LLM Engine Specifications
# =========================================================================
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()


# =========================================================================
# Settings Class
# =========================================================================
class Settings:
    """Application-wide configuration singleton."""

    PROJECT_NAME: str = "CyberVerse AI"
    API_V1_STR: str = "/api/v1"
    
    # Server configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = PORT
    
    # Database
    DATABASE_URL: str = DATABASE_URL
    
    # CORS
    raw_origins = os.getenv("CORS_ORIGINS")
    CORS_ORIGINS: list[str] = [o.strip() for o in raw_origins.split(",") if o.strip()] if raw_origins else [
        "https://cyber-verse-ai.vercel.app",
        "http://localhost:3000",
        "http://localhost:3005",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3005",
    ]
    
    # Cryptography
    SECRET_KEY: str = SECRET_KEY
    
    # Preferred Provider
    PREFERRED_LLM_PROVIDER: str = PREFERRED_LLM_PROVIDER
    
    # API Keys
    GROQ_API_KEY: str | None = GROQ_API_KEY
    OPENAI_API_KEY: str | None = OPENAI_API_KEY
    ANTHROPIC_API_KEY: str | None = ANTHROPIC_API_KEY
    
    # LLM Settings
    OLLAMA_API_BASE: str = OLLAMA_API_BASE
    OLLAMA_MODEL: str = OLLAMA_MODEL
    GROQ_MODEL: str = GROQ_MODEL


    # Redis / Celery
    REDIS_URL: str = REDIS_URL
    CELERY_QUEUE_NAME: str = os.getenv("CELERY_QUEUE_NAME", "celery")
    CELERY_TASK_TIME_LIMIT_SECONDS: int = int(os.getenv("CELERY_TASK_TIME_LIMIT_SECONDS", "1800"))
    CELERY_TASK_SOFT_TIME_LIMIT_SECONDS: int = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT_SECONDS", "1500"))

    # Rate limiting
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    RATE_LIMIT_REDIS_REQUIRED: bool = _get_bool("RATE_LIMIT_REDIS_REQUIRED", IS_PRODUCTION)

    # Scan runtime storage
    SCAN_WORKSPACE_ROOT: str = (
        os.getenv("SCAN_WORKSPACE_ROOT")
        or os.path.join(tempfile.gettempdir(), "cyberverse_scans")
    )
    MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
    GIT_CLONE_TIMEOUT_SECONDS: int = int(os.getenv("GIT_CLONE_TIMEOUT_SECONDS", "120"))
    GIT_CLONE_DEPTH: int = int(os.getenv("GIT_CLONE_DEPTH", "1"))

settings = Settings()

import os
import tempfile
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Resolve absolute path to .env file relative to this module
base_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=base_dir / ".env")



class Settings(BaseSettings):
    """Application-wide configuration settings powered by pydantic-settings."""

    PROJECT_NAME: str = "CyberVerse AI"
    API_V1_STR: str = "/api/v1"

    # Server configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8090

    # Database
    DATABASE_URL: str = "sqlite:///./instance/cyberverse.db"

    # CORS Origins list
    CORS_ORIGINS: List[str] = [
        "https://cyber-verse-ai.vercel.app",
        "http://localhost:3000",
        "http://localhost:3005",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3005",
    ]

    # Cryptography
    SECRET_KEY: str = "CYBER_VERSE_GLOWING_NEON_SECRET_2026"

    # Preferred Provider
    PREFERRED_LLM_PROVIDER: str = "groq"

    # API Keys
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    # LLM Settings
    OLLAMA_API_BASE: str = "http://localhost:11434/v1"
    OLLAMA_MODEL: str = "llama3"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_QUEUE_NAME: str = "celery"
    CELERY_TASK_TIME_LIMIT_SECONDS: int = 1800
    CELERY_TASK_SOFT_TIME_LIMIT_SECONDS: int = 1500

    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_REDIS_REQUIRED: bool = False


    # Scan runtime storage
    SCAN_WORKSPACE_ROOT: str = os.path.join(tempfile.gettempdir(), "cyberverse_scans")
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024
    GIT_CLONE_TIMEOUT_SECONDS: int = 120
    GIT_CLONE_DEPTH: int = 1

    class Config:
        env_file = ".env"
        extra = "ignore"

    def __init__(self, **values):
        # Override default values using current system environment state
        raw_origins = os.getenv("CORS_ORIGINS")
        if raw_origins:
            values["CORS_ORIGINS"] = [o.strip() for o in raw_origins.split(",") if o.strip()]

        raw_port = os.getenv("PORT")
        if raw_port:
            try:
                values["PORT"] = int(raw_port)
            except ValueError:
                pass

        raw_provider = os.getenv("PREFERRED_LLM_PROVIDER")
        if raw_provider:
            values["PREFERRED_LLM_PROVIDER"] = raw_provider.lower().strip()

        db_url = os.getenv("DATABASE_URL") or os.getenv("PG_DATABASE_URL")
        if db_url:
            values["DATABASE_URL"] = db_url

        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            values["REDIS_URL"] = redis_url.strip()

        # Handle SECRET_KEY dynamic fallbacks
        app_env = os.getenv("APP_ENV", "development").lower().strip()
        secret_key = os.getenv("SECRET_KEY")
        if not secret_key or secret_key.strip() in (
            "",
            "your-secret-key-here",
            "CYBER_VERSE_GLOWING_NEON_SECRET_2026",
            "REPLACE_ME_IN_PRODUCTION"
        ):
            if app_env != "production":
                import secrets
                values["SECRET_KEY"] = secrets.token_urlsafe(64)

        super().__init__(**values)


settings = Settings()

"""
Database migration management via Alembic.
Runs migrations at application startup with rollback support.
"""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.core.database import engine

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


def _alembic_config() -> Config:
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    return cfg


def run_migrations() -> None:
    """Apply all pending Alembic migrations (upgrade to head)."""
    cfg = _alembic_config()
    try:
        command.upgrade(cfg, "head")
        logger.info("Database migrations applied successfully")
    except Exception as e:
        err_msg = str(e).lower()
        if "already exists" in err_msg or "duplicate" in err_msg:
            logger.warning(
                "Tables already exist from prior schema; stamping Alembic head: %s", e
            )
            command.stamp(cfg, "head")
        else:
            logger.exception("Database migration failed: %s", e)
            raise


def rollback_migration(revisions: str = "-1") -> None:
    """Rollback database by N revisions (default: one step)."""
    try:
        command.downgrade(_alembic_config(), revisions)
        logger.info("Database rolled back %s revision(s)", revisions)
    except Exception as e:
        logger.exception("Database rollback failed: %s", e)
        raise


def verify_database_connection(max_retries: int = 5, retry_delay: float = 2.0) -> bool:
    """Verify database connectivity with exponential backoff retry."""
    import time
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("Database connection verified (attempt %d)", attempt)
            return True
        except OperationalError as e:
            logger.warning(
                "Database connection attempt %d/%d failed: %s",
                attempt, max_retries, e,
            )
            if attempt < max_retries:
                time.sleep(retry_delay * attempt)
    logger.error("Database connection failed after %d attempts", max_retries)
    return False


def initialize_database() -> None:
    """Full database initialization: verify connection, run migrations."""
    if not verify_database_connection():
        raise RuntimeError("Cannot connect to database after retries")
    run_migrations()

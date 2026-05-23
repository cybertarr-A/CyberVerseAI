import os
import logging
import time
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

logger = logging.getLogger("cyberverse.database")

CONNECT_MAX_RETRIES = int(os.getenv("DB_CONNECT_MAX_RETRIES", "5"))
CONNECT_RETRY_DELAY = float(os.getenv("DB_CONNECT_RETRY_DELAY", "2.0"))

# If SQLite is selected, ensure folder exists
if settings.DATABASE_URL.startswith("sqlite"):
    db_dir = os.path.dirname(settings.DATABASE_URL.replace("sqlite:///", ""))
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

# Create engine with appropriate configuration per database backend
connect_args: dict = {}
engine_kwargs: dict = {}

if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False, "timeout": 30}
else:
    # Production connection pool settings for PostgreSQL/MySQL
    engine_kwargs = {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,  # Validates connections before use
        "pool_recycle": 1800,   # Recycle connections after 30 minutes
    }

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    **engine_kwargs,
)

# Enable WAL mode for SQLite to improve concurrent read/write performance
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_wal_mode(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

logger.info("Database engine initialized for: %s", settings.DATABASE_URL.split("://")[0])


def verify_connection(max_retries: int = CONNECT_MAX_RETRIES) -> bool:
    """Verify database connectivity with retry/backoff."""
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except OperationalError as e:
            logger.warning(
                "Database connection attempt %d/%d failed: %s",
                attempt, max_retries, e,
            )
            if attempt < max_retries:
                time.sleep(CONNECT_RETRY_DELAY * attempt)
    return False


def get_db():
    """Dependency that provides a database session with guaranteed cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

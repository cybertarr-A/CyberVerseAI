import logging
from celery import Celery
from celery.signals import worker_ready

from app.core.config import settings

logger = logging.getLogger("cyberverse.celery")

REDIS_URL = settings.REDIS_URL

# Initialize Celery app
celery_app = Celery(
    "cyberverse_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Apply performance and production-grade task configuration
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # Tasks are acknowledged after execution for durability
    worker_prefetch_multiplier=1,  # Prevent pre-fetching for long running scanning tasks
    worker_max_tasks_per_child=50,  # Prevent memory leaks
    worker_max_memory_per_child=200000,  # Prevent memory bloat (max 200MB per child)
    broker_connection_retry_on_startup=True,  # Graceful startup recovery
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT_SECONDS,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT_SECONDS,
    task_reject_on_worker_lost=True,  # Re-queue task if worker crashes
    result_expires=3600,  # Expire stale results after 1 hour to prevent Redis memory bloat
    task_default_queue=settings.CELERY_QUEUE_NAME,
)

# Explicitly register tasks module for discovery
celery_app.conf.imports = [
    "app.tasks.scan_tasks",
    "app.tasks.analysis_tasks"
]


@worker_ready.connect
def validate_worker_config(sender, **kwargs):
    """Audits integration configurations when the Celery worker starts up."""
    logger.info("Celery worker booted successfully — starting dynamic environment checks")

    # 1. GROQ_API_KEY Check
    if not settings.GROQ_API_KEY or settings.GROQ_API_KEY.strip() in ("", "your_groq_api_key_here"):
        logger.error("Invalid configuration detected")
        raise ValueError("GROQ_API_KEY missing")

    # 2. REDIS_URL Check
    if not settings.REDIS_URL or settings.REDIS_URL.strip() == "":
        logger.error("Invalid configuration detected")
        raise ValueError("REDIS_URL is not set")

    # 3. DATABASE_URL Check
    if not settings.DATABASE_URL or settings.DATABASE_URL.strip() == "":
        logger.error("Invalid configuration detected")
        raise ValueError("DATABASE_URL is not set")

    # 4. CORS_ORIGINS Check
    if not isinstance(settings.CORS_ORIGINS, list):
        logger.error("Invalid configuration detected")
        raise ValueError("CORS_ORIGINS format invalid")

    logger.info("✓ Groq configured")
    logger.info("✓ Redis configured")
    logger.info("✓ Database configured")
    logger.info("✓ CORS configured")

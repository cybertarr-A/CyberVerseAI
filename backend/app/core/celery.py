import logging
from celery import Celery

from app.core.config import settings

logger = logging.getLogger(__name__)

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
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT_SECONDS,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT_SECONDS,
    task_reject_on_worker_lost=True,  # Re-queue task if worker crashes
    result_expires=3600,  # Expire stale results after 1 hour to prevent Redis memory bloat
    task_default_queue=settings.CELERY_QUEUE_NAME,
)

# Explicitly register tasks module for discovery
celery_app.conf.imports = ["app.tasks.scan_tasks"]

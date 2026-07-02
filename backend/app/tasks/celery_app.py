import logging
from celery import Celery
from celery.signals import setup_logging
from backend.app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "docscope_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

from backend.app.core.telemetry import instrument_celery
instrument_celery()


# Configure Celery settings
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600, # 1 hour max time limit
    task_default_queue="default",
    task_routes={
        "backend.app.tasks.tasks.*": {"queue": "ingestion"},
        "backend.app.tasks.ocr_tasks.ocr_task": {"queue": "ocr-pipeline"},
        "backend.app.tasks.ocr_tasks.docling_parse_task": {"queue": "ocr-pipeline"},
        "backend.app.tasks.ocr_tasks.bge_embed_task": {"queue": "embed-pipeline"},
        "backend.app.tasks.ocr_tasks.metadata_enrichment_task": {"queue": "metadata-pipeline"},
    },
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=10,
)

# Setup logger configuration for Celery worker
@setup_logging.connect
def config_loggers(*args, **kwds):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers
    if not logger.handlers:
        formatter = logging.Formatter(
            "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

# Autodiscover tasks from app/tasks directory
celery_app.autodiscover_tasks(["backend.app.tasks"])
import backend.app.tasks.partition_tasks
import backend.app.tasks.ocr_tasks


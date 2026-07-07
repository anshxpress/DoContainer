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


from backend.app.core.config import features

base_task_routes = {
    "backend.app.tasks.ocr_tasks.ocr_task": {"queue": "ocr-pipeline"},
    "backend.app.tasks.ocr_tasks.docling_parse_task": {"queue": "ocr-pipeline"},
    "backend.app.tasks.ocr_tasks.bge_embed_task": {"queue": "embed-pipeline"},
    "backend.app.tasks.ocr_tasks.metadata_enrichment_task": {"queue": "metadata-pipeline"},
    "backend.app.tasks.tasks.dlq_handler": {"queue": "ingestion-dlq"},
    "backend.app.tasks.tasks.*": {"queue": "default"},
}

if features.ENABLE_KNOWLEDGE_GRAPH:
    base_task_routes["backend.app.tasks.knowledge_graph_tasks.*"] = {"queue": "default"}
if features.ENABLE_ACL:
    base_task_routes["backend.app.tasks.retention_tasks.*"] = {"queue": "default"}

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
    task_routes=base_task_routes,
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

import time
import os
import psutil
from celery.signals import task_prerun, task_postrun, task_retry, task_failure

try:
    import torch
except ImportError:
    torch = None

task_start_times = {}

@task_prerun.connect
def task_prerun_handler(task_id, task, *args, **kwargs):
    task_start_times[task_id] = time.time()
    if torch and torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    
    task_logger = logging.getLogger(task.name)
    task_logger.info(f"[START] Task {task.name} ({task_id}) started.")

@task_postrun.connect
def task_postrun_handler(task_id, task, retval, state, *args, **kwargs):
    start_time = task_start_times.pop(task_id, time.time())
    duration = time.time() - start_time
    
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / (1024 * 1024)
    
    gpu_mb = 0.0
    if torch and torch.cuda.is_available():
        gpu_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
        
    task_logger = logging.getLogger(task.name)
    task_logger.info(f"[END] Task {task.name} ({task_id}) finished. "
                     f"[TIME] {duration:.2f}s "
                     f"[MEMORY] {mem_mb:.2f}MB "
                     f"[GPU] {gpu_mb:.2f}MB")

@task_retry.connect
def task_retry_handler(request, reason, einfo, *args, **kwargs):
    task_name = request.task.name if request.task else "unknown"
    task_logger = logging.getLogger(task_name)
    task_logger.warning(f"[RETRY] Task {task_name} ({request.id}) retrying. Reason: {reason}")

@task_failure.connect
def task_failure_handler(task_id, exception, args, kwargs, traceback, einfo, *task_args, **task_kwargs):
    sender = task_kwargs.get("sender")
    task_name = sender.name if sender else "unknown"
    task_logger = logging.getLogger(task_name)
    task_logger.error(f"[FAILED] Task {task_name} ({task_id}) failed. Error: {exception}")

# Autodiscover tasks from app/tasks directory
celery_app.autodiscover_tasks(["backend.app.tasks"])
import backend.app.tasks.partition_tasks
import backend.app.tasks.ocr_tasks

if features.ENABLE_KNOWLEDGE_GRAPH:
    import backend.app.tasks.knowledge_graph_tasks

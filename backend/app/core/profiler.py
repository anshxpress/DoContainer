import logging
import time
import uuid
from datetime import datetime, timezone
from contextlib import ContextDecorator
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.models.models import ProcessingMetrics, Document

logger = logging.getLogger(__name__)

class StageProfiler(ContextDecorator):
    """
    Context manager to profile a processing stage (upload, ocr, embedding, metadata, vision, qdrant).
    Records duration, CPU, and GPU memory usage and persists to ProcessingMetrics.
    """
    def __init__(
        self, 
        db: Session, 
        document_id: uuid.UUID, 
        org_id: uuid.UUID, 
        stage: str
    ):
        self.db = db
        self.document_id = document_id
        self.org_id = org_id
        self.stage = stage
        self.metric_record: Optional[ProcessingMetrics] = None
        self._start_time: Optional[float] = None
        
        # CPU/GPU Tracking states
        self._psutil = None
        try:
            import psutil
            self._psutil = psutil
        except ImportError:
            pass
            
        self._torch = None
        try:
            import torch
            if torch.cuda.is_available():
                self._torch = torch
        except ImportError:
            pass

    def __enter__(self):
        self._start_time = time.perf_counter()
        
        # Reset torch cuda stats if available to track peak memory for this block
        if self._torch:
            self._torch.cuda.reset_peak_memory_stats()
            
        # Initial call to psutil.cpu_percent (non-blocking, sets reference point)
        if self._psutil:
            self._psutil.cpu_percent(interval=None)

        self.metric_record = ProcessingMetrics(
            document_id=self.document_id,
            org_id=self.org_id,
            stage=self.stage,
            started_at=datetime.now(timezone.utc),
            status="in_progress"
        )
        self.db.add(self.metric_record)
        self.db.commit()
        self.db.refresh(self.metric_record)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._start_time or not self.metric_record:
            return False
            
        duration_ms = int((time.perf_counter() - self._start_time) * 1000)
        cpu_percent = 0.0
        gpu_memory_mb = 0.0
        
        if self._psutil:
            cpu_percent = self._psutil.cpu_percent(interval=None)
            
        if self._torch:
            # max_memory_allocated since reset
            peak_bytes = self._torch.cuda.max_memory_allocated()
            gpu_memory_mb = peak_bytes / (1024 * 1024)

        self.metric_record.ended_at = datetime.now(timezone.utc)
        self.metric_record.duration_ms = duration_ms
        self.metric_record.cpu_percent = round(cpu_percent, 2)
        self.metric_record.gpu_memory_mb = round(gpu_memory_mb, 2)
        
        if exc_type:
            self.metric_record.status = "failed"
            self.metric_record.error_message = str(exc_val)
        else:
            self.metric_record.status = "completed"

        try:
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to commit ProcessingMetrics for {self.stage}: {e}")
            self.db.rollback()
            
        return False  # Do not suppress exceptions

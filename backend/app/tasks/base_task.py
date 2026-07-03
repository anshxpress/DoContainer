from celery import Task
from celery.utils.log import get_task_logger
from backend.app.core.db import SessionLocal

logger = get_task_logger(__name__)

class DBSessionTask(Task):
    """
    Base Celery task that provides a SQLAlchemy session lifecycle management
    and standardized error handling.
    """
    _db = None

    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        if self._db is not None:
            self._db.close()
            self._db = None

import logging
from sqlalchemy import text
from backend.app.tasks.celery_app import celery_app
from backend.app.core.db import SessionLocal

logger = logging.getLogger(__name__)

@celery_app.task(name="backend.app.tasks.partition_tasks.create_monthly_partitions_task")
def create_monthly_partitions_task() -> None:
    """
    Day 1: Dynamically pre-create range partitions for the current and next month.
    """
    logger.info("Executing create_monthly_partitions_task...")
    db = SessionLocal()
    try:
        db.execute(text("SELECT create_monthly_partitions();"))
        db.commit()
        logger.info("Monthly partitions successfully checked/created.")
    except Exception as e:
        logger.error(f"Failed to execute create_monthly_partitions_task: {e}")
        db.rollback()
    finally:
        db.close()


from typing import Optional

@celery_app.task(name="backend.app.tasks.partition_tasks.log_audit_event_task")
def log_audit_event_task(
    user_id_str: Optional[str],
    ip_address: Optional[str],
    action: str,
    resource: Optional[str],
    metadata_json: Optional[str]
) -> None:
    """
    Day 2: Log audit actions to the database asynchronously.
    Skipped in Personal mode (ENABLE_AUDIT=False).
    """
    from backend.app.core.config import features
    if not features.ENABLE_AUDIT:
        return  # Audit logging disabled in Personal mode

    logger.info(f"Logging audit event: {action} by user {user_id_str}")
    db = SessionLocal()
    try:
        user_uuid = None
        org_uuid = None
        if user_id_str:
            import uuid
            try:
                user_uuid = uuid.UUID(user_id_str)
                # Look up user membership to find org_id
                from backend.app.models.models import Membership
                membership = db.query(Membership).filter(Membership.user_id == user_uuid).first()
                if membership:
                    org_uuid = membership.org_id
            except Exception as lookup_err:
                logger.error(f"Failed to resolve user/org in audit: {lookup_err}")

        from backend.app.models.models import AuditLog
        import uuid
        audit_log = AuditLog(
            id=uuid.uuid4(),
            user_id=user_uuid,
            org_id=org_uuid,
            ip_address=ip_address,
            action=action,
            resource=resource,
            metadata_json=metadata_json
        )
        db.add(audit_log)
        db.commit()
        logger.info("Audit log successfully persisted.")
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")
        db.rollback()
    finally:
        db.close()



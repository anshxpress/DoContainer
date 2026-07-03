"""
Sprint 11 - Retention Celery Tasks
Executes retention policies nightly.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from celery import shared_task

from backend.app.core.db import SessionLocal
from backend.app.models.models import Document, RetentionPolicy
from backend.app.core.s3 import s3_storage
from backend.app.core.qdrant import qdrant_client
from backend.app.core.config import settings

logger = logging.getLogger(__name__)


@shared_task(name="backend.app.tasks.retention_tasks.apply_retention_policies")
def apply_retention_policies() -> dict:
    """
    Finds documents that have exceeded their retention policy timeframe and processes them.
    If auto_delete is True, the document and its S3/Qdrant assets are deleted.
    If False, the document is archived (is_archived = True).
    """
    logger.info("[retention] Starting retention policy sweep...")
    db = SessionLocal()
    processed_count = 0
    deleted_count = 0
    expired_count = 0

    try:
        policies = db.query(RetentionPolicy).all()

        for policy in policies:
            # Calculate the cutoff date based on the policy's retain_days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=policy.retain_days)

            # Build query for documents matching this policy
            query = db.query(Document).filter(
                Document.org_id == policy.org_id,
                Document.created_at < cutoff_date,
            )

            # Exclude already processed documents
            if policy.auto_delete:
                # If auto_delete, we only care about documents that haven't been deleted yet
                pass
            else:
                # If not auto_delete, we only care about documents not already archived
                query = query.filter(Document.is_archived == False)

            if policy.folder_id:
                query = query.filter(Document.folder_id == policy.folder_id)

            docs_to_process = query.all()

            for doc in docs_to_process:
                processed_count += 1
                if policy.auto_delete:
                    # 1. Delete from S3
                    try:
                        # Assuming documents are stored under their org_id/doc_id prefix
                        prefix = f"{doc.org_id}/{doc.id}/"
                        objects_to_delete = s3_storage.client.list_objects_v2(
                            Bucket=s3_storage.bucket_name, Prefix=prefix
                        )
                        if "Contents" in objects_to_delete:
                            delete_keys = [{"Key": obj["Key"]} for obj in objects_to_delete["Contents"]]
                            s3_storage.client.delete_objects(
                                Bucket=s3_storage.bucket_name,
                                Delete={"Objects": delete_keys}
                            )
                    except Exception as e:
                        logger.error(f"[retention] Failed to delete S3 objects for {doc.id}: {e}")

                    # 2. Delete from Qdrant
                    try:
                        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
                        delete_filter = Filter(
                            must=[FieldCondition(key="document_id", match=MatchValue(value=str(doc.id)))]
                        )
                        qdrant_client.delete(
                            collection_name=settings.QDRANT_TEXT_COLLECTION_NAME,
                            points_selector=delete_filter
                        )
                    except Exception as e:
                         logger.error(f"[retention] Failed to delete Qdrant points for {doc.id}: {e}")

                    # 3. Delete from Postgres (cascades)
                    db.delete(doc)
                    deleted_count += 1
                    logger.info(f"[retention] Auto-deleted document {doc.id} per policy {policy.id}")

                else:
                    # Just flag as archived
                    doc.is_archived = True
                    expired_count += 1
                    logger.info(f"[retention] Marked document {doc.id} as archived per policy {policy.id}")
        
        db.commit()

    except Exception as exc:
        db.rollback()
        logger.error(f"[retention] Error applying retention policies: {exc}")
        raise
    finally:
        db.close()

    logger.info(f"[retention] Sweep completed: {processed_count} checked, {deleted_count} deleted, {expired_count} expired.")
    return {
        "processed_count": processed_count,
        "deleted_count": deleted_count,
        "expired_count": expired_count
    }

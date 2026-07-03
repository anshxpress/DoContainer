"""
Sprint 10 - Storage Cleanup API
POST /api/v1/admin/storage/cleanup  - remove orphaned S3 objects and Qdrant points
GET  /api/v1/admin/storage/stats    - show storage usage breakdown
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user_context, CurrentUserContext, get_db
from backend.app.core.cache import invalidate_pattern
from backend.app.core.s3 import s3_storage
from backend.app.core.qdrant import qdrant_client
from backend.app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/storage/stats")
def storage_stats(
    current_context: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Return storage breakdown: DB row counts, Redis cache key counts,
    and Qdrant collection point counts.
    """
    try:
        tables = [
            "documents", "document_pages", "document_parse_elements",
            "ocr_chunks", "text_embedding_chunks", "document_summaries",
        ]
        db_counts = {}
        for table in tables:
            try:
                row = db.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()
                db_counts[table] = row[0] if row else 0
            except Exception:
                db_counts[table] = -1

        qdrant_info = {}
        try:
            for col_name in [settings.QDRANT_COLLECTION_NAME, settings.QDRANT_TEXT_COLLECTION_NAME]:
                info = qdrant_client.get_collection(col_name)
                qdrant_info[col_name] = info.points_count
        except Exception as e:
            qdrant_info["error"] = str(e)

        redis_stats = {}
        try:
            from backend.app.core.cache import redis_client
            if redis_client:
                info = redis_client.info("memory")
                redis_stats["used_memory_human"] = info.get("used_memory_human", "n/a")
                redis_stats["used_memory_mb"] = round(info.get("used_memory", 0) / 1024 / 1024, 2)
                redis_stats["total_keys"] = redis_client.dbsize()
        except Exception as e:
            redis_stats["error"] = str(e)

        return {
            "db_row_counts": db_counts,
            "qdrant_point_counts": qdrant_info,
            "redis": redis_stats,
        }
    except Exception as exc:
        logger.error("Storage stats error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/storage/cleanup")
def storage_cleanup(
    current_context: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Cleanup orphaned artifacts:
    1. S3 page images for documents that no longer exist in DB
    2. Qdrant points for deleted documents
    3. Stale Redis cache keys (search + embed namespaces)
    """
    report: Dict[str, Any] = {
        "s3_objects_deleted": 0,
        "qdrant_points_purged": 0,
        "redis_keys_deleted": 0,
        "errors": [],
    }

    # Redis: invalidate stale search and embed caches
    try:
        report["redis_keys_deleted"] += invalidate_pattern("search")
        report["redis_keys_deleted"] += invalidate_pattern("embed")
        logger.info("Cleaned %d Redis cache keys", report["redis_keys_deleted"])
    except Exception as e:
        report["errors"].append(f"Redis cleanup error: {e}")

    # S3: find page objects for non-existent documents
    try:
        result = s3_storage.client.list_objects_v2(
            Bucket=s3_storage.bucket_name,
            MaxKeys=1000,
        )
        orphan_keys = []
        for obj in result.get("Contents", []):
            key = obj["Key"]
            parts = key.split("/")
            if len(parts) >= 3:
                possible_doc_id = parts[1]
                try:
                    doc_uuid = uuid.UUID(possible_doc_id)
                    row = db.execute(
                        text("SELECT id FROM documents WHERE id = :did"),
                        {"did": str(doc_uuid)},
                    ).fetchone()
                    if row is None:
                        orphan_keys.append(key)
                except ValueError:
                    pass

        for orphan_key in orphan_keys[:100]:  # cap at 100 per run
            try:
                s3_storage.client.delete_object(Bucket=s3_storage.bucket_name, Key=orphan_key)
                report["s3_objects_deleted"] += 1
            except Exception as e:
                report["errors"].append(f"S3 delete error {orphan_key}: {e}")
        logger.info("Deleted %d orphan S3 objects", report["s3_objects_deleted"])
    except Exception as e:
        report["errors"].append(f"S3 cleanup error: {e}")

    # Qdrant: scroll and purge points for non-existent documents
    try:
        offset = None
        purged = 0
        for collection in [settings.QDRANT_TEXT_COLLECTION_NAME]:
            while True:
                scroll_result = qdrant_client.scroll(
                    collection_name=collection,
                    limit=200,
                    with_payload=["document_id"],
                    offset=offset,
                )
                points, next_offset = scroll_result
                if not points:
                    break

                dead_ids = []
                for point in points:
                    doc_id_str = (point.payload or {}).get("document_id")
                    if doc_id_str:
                        row = db.execute(
                            text("SELECT id FROM documents WHERE id = :did"),
                            {"did": doc_id_str},
                        ).fetchone()
                        if row is None:
                            dead_ids.append(str(point.id))

                if dead_ids:
                    from qdrant_client.models import PointIdsList
                    qdrant_client.delete(
                        collection_name=collection,
                        points_selector=PointIdsList(points=dead_ids),
                    )
                    purged += len(dead_ids)

                if next_offset is None:
                    break
                offset = next_offset

        report["qdrant_points_purged"] = purged
        logger.info("Purged %d orphan Qdrant points", purged)
    except Exception as e:
        report["errors"].append(f"Qdrant cleanup error: {e}")

    return report

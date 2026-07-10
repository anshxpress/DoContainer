import json
import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from backend.app.models.models import UsageMetric, Document, AuditLog, User

logger = logging.getLogger(__name__)

def log_usage_metric(
    db: Session,
    org_id: uuid.UUID,
    metric_type: str,
    value: float,
    metadata: Optional[Dict[str, Any]] = None
) -> UsageMetric:
    """
    Log a usage telemetry detail to the usage_metrics table.
    metric_type can be: "pages_rendered", "storage_bytes", or "api_tokens"
    """
    try:
        metadata_str = json.dumps(metadata) if metadata else None
        metric = UsageMetric(
            id=uuid.uuid4(),
            org_id=org_id,
            metric_type=metric_type,
            value=value,
            metadata_json=metadata_str,
            created_at=datetime.now(timezone.utc)
        )
        db.add(metric)
        db.commit()
        logger.info(f"Recorded usage metric: {metric_type} = {value} for org {org_id}")
        return metric
    except Exception as e:
        logger.error(f"Failed to write usage metric: {e}")
        db.rollback()
        raise e


def get_aggregated_metrics(db: Session, org_id: uuid.UUID) -> Dict[str, Any]:
    """
    Day 3: Fetch analytics details from the database.
    Gathers totals and trend lines for Next.js dashboard widgets.
    """
    from backend.app.core.config import features

    # 1. Total Documents
    total_docs = db.query(func.count(Document.id)).filter(Document.org_id == org_id).scalar() or 0

    # 2. Pages Rendered Total
    pages_rendered = db.query(func.sum(UsageMetric.value))\
        .filter(UsageMetric.org_id == org_id, UsageMetric.metric_type == "pages_rendered")\
        .scalar() or 0.0

    # 3. Storage Consumed Total (bytes)
    storage_bytes = db.query(func.sum(UsageMetric.value))\
        .filter(UsageMetric.org_id == org_id, UsageMetric.metric_type == "storage_bytes")\
        .scalar() or 0.0

    # 4. API Tokens Consumed Total
    api_tokens = db.query(func.sum(UsageMetric.value))\
        .filter(UsageMetric.org_id == org_id, UsageMetric.metric_type == "api_tokens")\
        .scalar() or 0.0

    # 5. Active User Count — only if audit is enabled
    if features.ENABLE_AUDIT:
        since_30_days = datetime.now(timezone.utc) - timedelta(days=30)
        active_users = db.query(func.count(func.distinct(AuditLog.user_id)))\
            .filter(AuditLog.org_id == org_id, AuditLog.created_at >= since_30_days)\
            .scalar() or 0
    else:
        active_users = 1  # Personal mode: single user

    # 6. Recent Audits — only if audit is enabled
    if features.ENABLE_AUDIT:
        recent_audits_query = db.query(AuditLog, User.email)\
            .outerjoin(User, User.id == AuditLog.user_id)\
            .filter(AuditLog.org_id == org_id)\
            .order_by(AuditLog.created_at.desc())\
            .limit(5)\
            .all()
        
        recent_audits_list = []
        for audit, email in recent_audits_query:
            recent_audits_list.append({
                "action": audit.action,
                "user": email or "system_admin",
                "time": audit.created_at.isoformat()
            })
    else:
        recent_audits_list = []


    # 7. Trends data (last 7 days of daily totals for Recharts charts)
    today = datetime.now(timezone.utc).date()
    daily_trends = []
    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        start_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(target_date, datetime.max.time(), tzinfo=timezone.utc)

        # Tokens daily total
        tokens_val = db.query(func.sum(UsageMetric.value))\
            .filter(
                UsageMetric.org_id == org_id,
                UsageMetric.metric_type == "api_tokens",
                UsageMetric.created_at >= start_dt,
                UsageMetric.created_at <= end_dt
            ).scalar() or 0.0

        # Pages rendered daily total
        pages_val = db.query(func.sum(UsageMetric.value))\
            .filter(
                UsageMetric.org_id == org_id,
                UsageMetric.metric_type == "pages_rendered",
                UsageMetric.created_at >= start_dt,
                UsageMetric.created_at <= end_dt
            ).scalar() or 0.0

        # Storage added daily total
        storage_val = db.query(func.sum(UsageMetric.value))\
            .filter(
                UsageMetric.org_id == org_id,
                UsageMetric.metric_type == "storage_bytes",
                UsageMetric.created_at >= start_dt,
                UsageMetric.created_at <= end_dt
            ).scalar() or 0.0

        daily_trends.append({
            "date": target_date.strftime("%b %d"),
            "tokens": int(tokens_val),
            "pages": int(pages_val),
            "storage_mb": round(storage_val / (1024 * 1024), 2)
        })

    # 8. File type breakdown
    # Query all completed documents to see formats
    file_types_query = db.query(Document.file_type, func.count(Document.id), func.sum(Document.file_size))\
        .filter(Document.org_id == org_id)\
        .group_by(Document.file_type)\
        .all()
    
    file_type_breakdown = []
    for ftype, count, size_bytes in file_types_query:
        file_type_breakdown.append({
            "name": ftype.upper(),
            "value": count,
            "size_mb": round((size_bytes or 0) / (1024 * 1024), 2)
        })

    return {
        "totals": {
            "documents": total_docs,
            "pages_rendered": int(pages_rendered),
            "storage_bytes": int(storage_bytes),
            "api_tokens": int(api_tokens),
            "active_users": active_users
        },
        "recent_audits": recent_audits_list,
        "daily_trends": daily_trends,
        "file_type_breakdown": file_type_breakdown
    }

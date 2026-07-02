import uuid
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.api.deps import get_current_user_context, CurrentUserContext, PermissionChecker
from backend.app.core.db import get_db
from backend.app.services.metrics_service import get_aggregated_metrics
from backend.app.models.models import ProcessingMetrics
from sqlalchemy import func

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Pydantic Response Schemas ---
class TotalsSchema(BaseModel):
    documents: int
    pages_rendered: int
    storage_bytes: int
    api_tokens: int
    active_users: int

class RecentAuditSchema(BaseModel):
    action: str
    user: str
    time: str

class DailyTrendSchema(BaseModel):
    date: str
    tokens: int
    pages: int
    storage_mb: float

class FileTypeBreakdownSchema(BaseModel):
    name: str
    value: int
    size_mb: float

class StagePerformanceSchema(BaseModel):
    stage: str
    avg_duration_ms: float
    avg_cpu_percent: float
    avg_gpu_memory_mb: float
    count: int

class DashboardAnalyticsResponse(BaseModel):
    totals: TotalsSchema
    recent_audits: List[RecentAuditSchema]
    daily_trends: List[DailyTrendSchema]
    file_type_breakdown: List[FileTypeBreakdownSchema]

# --- Route ---

@router.get("/dashboard", response_model=DashboardAnalyticsResponse)
def get_dashboard_analytics(
    current_context: CurrentUserContext = Depends(PermissionChecker("analytics:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/analytics/dashboard
    Returns aggregated metrics, search/audit logs, daily usage trends, and storage distribution by file type.
    """
    try:
        org_uuid = uuid.UUID(current_context.org_id)
        metrics = get_aggregated_metrics(db, org_uuid)
        return metrics
    except Exception as exc:
        logger.error(f"Error compiling analytics dashboard: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error compiling analytics dashboard: {str(exc)}"
        )

@router.get("/performance", response_model=List[StagePerformanceSchema])
def get_performance_metrics(
    current_context: CurrentUserContext = Depends(PermissionChecker("analytics:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/analytics/performance
    Returns average processing durations and resource usage per pipeline stage.
    """
    try:
        org_uuid = uuid.UUID(current_context.org_id)
        rows = db.query(
            ProcessingMetrics.stage,
            func.avg(ProcessingMetrics.duration_ms).label('avg_duration_ms'),
            func.avg(ProcessingMetrics.cpu_percent).label('avg_cpu_percent'),
            func.avg(ProcessingMetrics.gpu_memory_mb).label('avg_gpu_memory_mb'),
            func.count(ProcessingMetrics.id).label('count')
        ).filter(
            ProcessingMetrics.org_id == org_uuid,
            ProcessingMetrics.status == 'completed'
        ).group_by(ProcessingMetrics.stage).all()

        results = []
        for row in rows:
            results.append({
                "stage": row.stage,
                "avg_duration_ms": float(row.avg_duration_ms or 0),
                "avg_cpu_percent": float(row.avg_cpu_percent or 0),
                "avg_gpu_memory_mb": float(row.avg_gpu_memory_mb or 0),
                "count": row.count,
            })
        return results
    except Exception as exc:
        logger.error(f"Error fetching performance metrics: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

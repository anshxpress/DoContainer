import uuid
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.api.deps import get_current_user_context, CurrentUserContext, PermissionChecker
from backend.app.core.db import get_db
from backend.app.services.metrics_service import get_aggregated_metrics

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

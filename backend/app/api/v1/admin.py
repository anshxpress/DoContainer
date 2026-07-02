import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
import uuid
from datetime import datetime

from backend.app.api.deps import get_current_user_context, CurrentUserContext, PermissionChecker
from backend.app.core.db import get_db
from backend.app.models.models import User, Organization, Membership, Role, Team, TeamMembership, Permission, Folder

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Response Schemas ---

class AdminUserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    team: str
    status: str
    initials: str
    joined: str

class AdminTeamResponse(BaseModel):
    id: str
    name: str
    members: int
    folders: int
    acl: str

class AdminPermissionResponse(BaseModel):
    action: str
    desc: str
    roles: Dict[str, bool]

class FailedJobResponse(BaseModel):
    id: str
    task_name: str
    task_id: str
    error: str
    status: str
    created_at: str

class HardwareResponse(BaseModel):
    cpu_percent: float
    memory_percent: float
    gpu_usage: Optional[float]

# --- Endpoints ---

@router.get("/users", response_model=List[AdminUserResponse])
def get_admin_users(
    current_context: CurrentUserContext = Depends(PermissionChecker("manage:users")),
    db: Session = Depends(get_db)
):
    """
    Fetch all users within the organization, including their roles and teams.
    """
    org_id = uuid.UUID(current_context.org_id)
    
    # Get all memberships for the org
    memberships = db.query(Membership).filter(Membership.org_id == org_id).all()
    
    result = []
    for m in memberships:
        user = m.user
        role = m.role.name if m.role else "Unknown"
        
        # Get team for user in this org
        team_name = "Unassigned"
        team_membership = db.query(TeamMembership).join(Team).filter(
            TeamMembership.user_id == user.id,
            Team.org_id == org_id
        ).first()
        
        if team_membership:
            team_name = team_membership.team.name
            
        # Build Name & Initials
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown User"
        initials = "".join([n[0].upper() for n in name.split()[:2]]) if name else "U"
        
        # Build Joined date
        joined = user.created_at.strftime("%b %d, %Y") if user.created_at else "Unknown"
        
        result.append(AdminUserResponse(
            id=str(user.id),
            name=name,
            email=user.email,
            role=role,
            team=team_name,
            status="active" if user.is_active else "inactive",
            initials=initials,
            joined=joined
        ))
        
    return result

@router.get("/teams", response_model=List[AdminTeamResponse])
def get_admin_teams(
    current_context: CurrentUserContext = Depends(PermissionChecker("manage:teams")),
    db: Session = Depends(get_db)
):
    """
    Fetch all teams within the organization.
    """
    org_id = uuid.UUID(current_context.org_id)
    teams = db.query(Team).filter(Team.org_id == org_id).all()
    
    result = []
    for team in teams:
        members_count = db.query(func.count(TeamMembership.user_id)).filter(TeamMembership.team_id == team.id).scalar()
        folders_count = db.query(func.count(Folder.id)).filter(Folder.team_id == team.id).scalar()
        
        result.append(AdminTeamResponse(
            id=str(team.id),
            name=team.name,
            members=members_count or 0,
            folders=folders_count or 0,
            acl="Read + Write" # Placeholder for team-level ACL logic
        ))
        
    return result

@router.get("/roles", response_model=List[AdminPermissionResponse])
def get_admin_roles_and_permissions(
    current_context: CurrentUserContext = Depends(PermissionChecker("manage:roles")),
    db: Session = Depends(get_db)
):
    """
    Fetch all permissions and the roles that have them.
    Builds a matrix matching the UI layout.
    """
    org_id = uuid.UUID(current_context.org_id)
    
    # We want system roles and org-specific roles
    roles = db.query(Role).filter((Role.org_id == None) | (Role.org_id == org_id)).all()
    
    # All system permissions
    permissions = db.query(Permission).all()
    
    result = []
    for perm in permissions:
        # Build roles dict: { "Org Admin": True, "Team Admin": False ... }
        roles_dict = {}
        for r in roles:
            has_perm = db.query(Permission).join(Role.permissions).filter(
                Role.id == r.id, 
                Permission.id == perm.id
            ).first() is not None
            roles_dict[r.name] = has_perm
            
        result.append(AdminPermissionResponse(
            action=perm.name,
            desc=perm.description or perm.name,
            roles=roles_dict
        ))
        
    return result

# ---------------------------------------------------------------------------
# Sprint 6: Observability and Operations Dashboards
# ---------------------------------------------------------------------------

@router.get("/jobs/status")
def get_jobs_status(
    current_context: CurrentUserContext = Depends(PermissionChecker("manage:system")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/admin/jobs/status
    Retrieves current job queue status from Celery via Redis broker.
    """
    try:
        from backend.app.tasks.celery_app import celery_app
        # Inspect active, reserved, and scheduled jobs
        i = celery_app.control.inspect()
        active = i.active() or {}
        reserved = i.reserved() or {}
        
        active_count = sum(len(tasks) for tasks in active.values())
        reserved_count = sum(len(tasks) for tasks in reserved.values())
        
        # We can also get document status aggregate
        from backend.app.models.models import Document
        docs_processing = db.query(Document).filter(Document.status.in_(["queued", "processing"])).count()
        
        return {
            "active_celery_jobs": active_count,
            "queued_celery_jobs": reserved_count,
            "documents_processing": docs_processing
        }
    except Exception as exc:
        logger.error(f"Failed to retrieve jobs status: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve jobs status")

@router.get("/jobs/failed", response_model=List[FailedJobResponse])
def get_failed_jobs(
    limit: int = 50,
    current_context: CurrentUserContext = Depends(PermissionChecker("manage:system")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/admin/jobs/failed
    Retrieves the terminal failures from the Dead Letter Queue database table.
    """
    from backend.app.models.models import FailedJob
    jobs = db.query(FailedJob).order_by(FailedJob.created_at.desc()).limit(limit).all()
    
    return [
        FailedJobResponse(
            id=str(job.id),
            task_name=job.task_name,
            task_id=job.task_id,
            error=job.error,
            status=job.status,
            created_at=job.created_at.isoformat() if job.created_at else ""
        ) for job in jobs
    ]

@router.post("/jobs/{failed_job_id}/retry")
def retry_failed_job(
    failed_job_id: uuid.UUID,
    current_context: CurrentUserContext = Depends(PermissionChecker("manage:system")),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/admin/jobs/{failed_job_id}/retry
    Re-queues a failed job from the DLQ back into the Celery pipeline.
    """
    from backend.app.models.models import FailedJob
    from backend.app.tasks.celery_app import celery_app
    
    job = db.query(FailedJob).filter(FailedJob.id == failed_job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Failed job not found")
        
    if job.status == "retried":
        raise HTTPException(status_code=400, detail="Job already retried")
        
    try:
        celery_app.send_task(
            job.task_name,
            args=job.args or [],
            kwargs=job.kwargs or {}
        )
        job.status = "retried"
        db.commit()
        return {"status": "retried", "task_name": job.task_name}
    except Exception as exc:
        logger.error(f"Failed to retry job {failed_job_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to re-queue job")

@router.get("/system/hardware", response_model=HardwareResponse)
def get_system_hardware(
    current_context: CurrentUserContext = Depends(PermissionChecker("manage:system")),
):
    """
    GET /api/v1/admin/system/hardware
    Retrieves current hardware utilization metrics for the dashboard.
    """
    import psutil
    gpu_usage = None
    try:
        import torch
        if torch.cuda.is_available():
            # Use torch memory as proxy for GPU usage
            gpu_mem = torch.cuda.memory_allocated() / torch.cuda.max_memory_allocated() if torch.cuda.max_memory_allocated() else 0
            gpu_usage = gpu_mem * 100.0
    except ImportError:
        pass
        
    return HardwareResponse(
        cpu_percent=psutil.cpu_percent(interval=0.1),
        memory_percent=psutil.virtual_memory().percent,
        gpu_usage=gpu_usage
    )

@router.get("/pipeline/metrics")
def get_pipeline_metrics(
    current_context: CurrentUserContext = Depends(PermissionChecker("manage:system")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/admin/pipeline/metrics
    Provides a quick view of pipeline durations: OCR, Embedding, and Search Latency.
    """
    from backend.app.models.models import ProcessingMetrics
    from backend.app.repositories.base_repo import search_log_repo
    
    try:
        # Pipeline averages
        pipeline_stats = db.query(
            ProcessingMetrics.stage,
            func.avg(ProcessingMetrics.duration_ms).label('avg_duration')
        ).filter(ProcessingMetrics.status == 'completed').group_by(ProcessingMetrics.stage).all()
        
        # Search latency average
        search_latency = db.query(
            func.avg(search_log_repo.model.latency_ms)
        ).scalar()
        
        stages = {row[0]: float(row[1]) for row in pipeline_stats}
        
        return {
            "ocr_time_ms": stages.get("ocr_task", 0.0),
            "embedding_time_ms": stages.get("embed_and_index_task", 0.0) + stages.get("bge_embed_task", 0.0),
            "search_latency_ms": float(search_latency or 0.0)
        }
    except Exception as exc:
        logger.error(f"Failed to retrieve pipeline metrics: {exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve pipeline metrics")

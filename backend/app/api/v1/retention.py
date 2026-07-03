"""
Sprint 11 - Retention Policy API
GET    /admin/retention/policies         - list org policies
POST   /admin/retention/policies         - create policy
DELETE /admin/retention/policies/{id}    - remove policy
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user_context, CurrentUserContext, get_db, PermissionChecker
from backend.app.models.models import RetentionPolicy, Folder

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class RetentionPolicyCreate(BaseModel):
    name: str
    retain_days: int
    auto_delete: bool = False
    scope: str  # "org" or "folder"
    folder_id: Optional[str] = None


class RetentionPolicyResponse(BaseModel):
    id: str
    name: str
    retain_days: int
    auto_delete: bool
    folder_id: Optional[str]
    created_by: Optional[str]
    created_at: datetime


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/retention/policies", response_model=List[RetentionPolicyResponse])
def list_retention_policies(
    current_context: CurrentUserContext = Depends(PermissionChecker("manage:retention")),
    db: Session = Depends(get_db),
) -> Any:
    """List all retention policies for the organization."""
    policies = db.query(RetentionPolicy).filter(
        RetentionPolicy.org_id == uuid.UUID(current_context.org_id)
    ).all()

    return [
        RetentionPolicyResponse(
            id=str(p.id),
            name=p.name,
            retain_days=p.retain_days,
            auto_delete=p.auto_delete,
            folder_id=str(p.folder_id) if p.folder_id else None,
            created_by=str(p.created_by) if p.created_by else None,
            created_at=p.created_at,
        )
        for p in policies
    ]


@router.post("/retention/policies", response_model=RetentionPolicyResponse, status_code=201)
def create_retention_policy(
    body: RetentionPolicyCreate,
    current_context: CurrentUserContext = Depends(PermissionChecker("manage:retention")),
    db: Session = Depends(get_db),
) -> Any:
    """Create a new retention policy scoped to the org or a specific folder."""
    if body.retain_days < 1:
        raise HTTPException(status_code=400, detail="retain_days must be >= 1")

    folder_uuid = None
    if body.scope == "folder":
        if not body.folder_id:
            raise HTTPException(status_code=400, detail="folder_id is required for folder scope")
        folder_uuid = uuid.UUID(body.folder_id)
        # Verify folder exists in this org
        folder = db.query(Folder).filter(
            Folder.id == folder_uuid,
            Folder.org_id == uuid.UUID(current_context.org_id)
        ).first()
        if not folder:
            raise HTTPException(status_code=404, detail="Folder not found")
    elif body.scope != "org":
        raise HTTPException(status_code=400, detail="scope must be 'org' or 'folder'")

    policy = RetentionPolicy(
        org_id=uuid.UUID(current_context.org_id),
        folder_id=folder_uuid,
        name=body.name,
        retain_days=body.retain_days,
        auto_delete=body.auto_delete,
        created_by=current_context.user.id,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)

    logger.info(
        "[retention] Created policy %s (retain_days=%d, auto_delete=%s) by %s",
        policy.id, policy.retain_days, policy.auto_delete, current_context.user.id
    )

    return RetentionPolicyResponse(
        id=str(policy.id),
        name=policy.name,
        retain_days=policy.retain_days,
        auto_delete=policy.auto_delete,
        folder_id=str(policy.folder_id) if policy.folder_id else None,
        created_by=str(policy.created_by) if policy.created_by else None,
        created_at=policy.created_at,
    )


@router.delete("/retention/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_retention_policy(
    policy_id: str,
    current_context: CurrentUserContext = Depends(PermissionChecker("manage:retention")),
    db: Session = Depends(get_db),
):
    """Delete a retention policy."""
    policy = db.query(RetentionPolicy).filter(
        RetentionPolicy.id == uuid.UUID(policy_id),
        RetentionPolicy.org_id == uuid.UUID(current_context.org_id),
    ).first()

    if not policy:
        raise HTTPException(status_code=404, detail="Retention policy not found")

    db.delete(policy)
    db.commit()
    logger.info("[retention] Deleted policy %s by %s", policy_id, current_context.user.id)

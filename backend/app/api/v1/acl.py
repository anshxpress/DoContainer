"""
Sprint 11 - Document ACL API
GET    /documents/{id}/acl         - list ACL entries
POST   /documents/{id}/acl         - grant permission
DELETE /documents/{id}/acl/{entry} - revoke permission
GET    /documents/{id}/acl/check   - check if current user has a permission (for frontend gates)
"""
from __future__ import annotations

import uuid
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.deps import (
    get_current_user_context, CurrentUserContext, get_db,
    PermissionChecker, check_document_permission,
)
from backend.app.models.models import DocumentACL, Document

router = APIRouter()
logger = logging.getLogger(__name__)

VALID_PRINCIPAL_TYPES = {"user", "team", "role"}
VALID_PERMISSIONS = {"read", "write", "approve", "download"}


# ── Schemas ──────────────────────────────────────────────────────────────────

class ACLGrantRequest(BaseModel):
    principal_type: str   # user | team | role
    principal_id: str     # UUID of user/team/role
    permission: str       # read | write | approve | download


class ACLEntryResponse(BaseModel):
    id: str
    document_id: str
    principal_type: str
    principal_id: str
    permission: str
    granted_by: Optional[str]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_doc_or_404(db: Session, document_id: str, org_id: str) -> Document:
    doc = db.query(Document).filter(
        Document.id == uuid.UUID(document_id),
        Document.org_id == uuid.UUID(org_id),
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _entry_to_response(e: DocumentACL) -> ACLEntryResponse:
    return ACLEntryResponse(
        id=str(e.id),
        document_id=str(e.document_id),
        principal_type=e.principal_type,
        principal_id=str(e.principal_id),
        permission=e.permission,
        granted_by=str(e.granted_by) if e.granted_by else None,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/documents/{document_id}/acl", response_model=List[ACLEntryResponse])
def list_acl(
    document_id: str,
    current_context: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> Any:
    """List all ACL entries for a document."""
    doc = _get_doc_or_404(db, document_id, current_context.org_id)

    if not check_document_permission(db, document_id, current_context, "read"):
        raise HTTPException(status_code=403, detail="Access denied")

    entries = db.query(DocumentACL).filter(DocumentACL.document_id == doc.id).all()
    return [_entry_to_response(e) for e in entries]


@router.post("/documents/{document_id}/acl", response_model=ACLEntryResponse, status_code=201)
def grant_acl(
    document_id: str,
    body: ACLGrantRequest,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:acl:manage")),
    db: Session = Depends(get_db),
) -> Any:
    """Grant a permission to a user, team, or role for a specific document."""
    if body.principal_type not in VALID_PRINCIPAL_TYPES:
        raise HTTPException(status_code=400, detail=f"principal_type must be one of {VALID_PRINCIPAL_TYPES}")
    if body.permission not in VALID_PERMISSIONS:
        raise HTTPException(status_code=400, detail=f"permission must be one of {VALID_PERMISSIONS}")

    doc = _get_doc_or_404(db, document_id, current_context.org_id)

    # Check for duplicate
    existing = db.query(DocumentACL).filter(
        DocumentACL.document_id == doc.id,
        DocumentACL.principal_type == body.principal_type,
        DocumentACL.principal_id == uuid.UUID(body.principal_id),
        DocumentACL.permission == body.permission,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="ACL entry already exists")

    entry = DocumentACL(
        document_id=doc.id,
        org_id=doc.org_id,
        principal_type=body.principal_type,
        principal_id=uuid.UUID(body.principal_id),
        permission=body.permission,
        granted_by=current_context.user.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    logger.info(
        "[acl] Granted %s:%s on document %s to %s/%s by %s",
        body.principal_type, body.permission, document_id,
        body.principal_type, body.principal_id, current_context.user.id
    )
    return _entry_to_response(entry)


@router.delete("/documents/{document_id}/acl/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_acl(
    document_id: str,
    entry_id: str,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:acl:manage")),
    db: Session = Depends(get_db),
):
    """Revoke an ACL entry."""
    doc = _get_doc_or_404(db, document_id, current_context.org_id)

    entry = db.query(DocumentACL).filter(
        DocumentACL.id == uuid.UUID(entry_id),
        DocumentACL.document_id == doc.id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="ACL entry not found")

    db.delete(entry)
    db.commit()
    logger.info("[acl] Revoked ACL entry %s on document %s by %s", entry_id, document_id, current_context.user.id)


@router.get("/documents/{document_id}/acl/check")
def check_my_permission(
    document_id: str,
    permission: str = "read",
    current_context: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Check if the current user has a given permission on this document (for frontend gates)."""
    _get_doc_or_404(db, document_id, current_context.org_id)
    allowed = check_document_permission(db, document_id, current_context, permission)
    return {"document_id": document_id, "permission": permission, "allowed": allowed}

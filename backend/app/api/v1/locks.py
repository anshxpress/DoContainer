"""
Sprint 11 - File Locking API
POST   /documents/{id}/lock   - acquire exclusive lock (30 min TTL)
DELETE /documents/{id}/lock   - release lock
GET    /documents/{id}/lock   - check lock status
PUT    /documents/{id}/lock   - renew lock (extend TTL)
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user_context, CurrentUserContext, get_db, PermissionChecker
from backend.app.models.models import DocumentLock, Document

router = APIRouter()
logger = logging.getLogger(__name__)

LOCK_TTL_MINUTES = 30


# ── Schemas ──────────────────────────────────────────────────────────────────

class LockRequest(BaseModel):
    reason: Optional[str] = None
    ttl_minutes: int = LOCK_TTL_MINUTES


class LockResponse(BaseModel):
    document_id: str
    locked: bool
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    lock_reason: Optional[str] = None
    is_own_lock: bool = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_doc_or_404(db: Session, document_id: str, org_id: str) -> Document:
    doc = db.query(Document).filter(
        Document.id == uuid.UUID(document_id),
        Document.org_id == uuid.UUID(org_id),
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


def _is_lock_expired(lock: DocumentLock) -> bool:
    return datetime.now(timezone.utc) > lock.expires_at.replace(tzinfo=timezone.utc)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/documents/{document_id}/lock", response_model=LockResponse)
def get_lock_status(
    document_id: str,
    current_context: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> Any:
    """Check whether a document is currently locked."""
    doc = _get_doc_or_404(db, document_id, current_context.org_id)

    lock = db.query(DocumentLock).filter(DocumentLock.document_id == doc.id).first()
    if not lock or _is_lock_expired(lock):
        # Clean up expired lock row
        if lock:
            db.delete(lock)
            db.commit()
        return LockResponse(document_id=document_id, locked=False)

    return LockResponse(
        document_id=document_id,
        locked=True,
        locked_by=str(lock.locked_by),
        locked_at=lock.locked_at,
        expires_at=lock.expires_at,
        lock_reason=lock.lock_reason,
        is_own_lock=lock.locked_by == current_context.user.id,
    )


@router.post("/documents/{document_id}/lock", response_model=LockResponse)
def acquire_lock(
    document_id: str,
    body: LockRequest,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:lock")),
    db: Session = Depends(get_db),
) -> Any:
    """Acquire an exclusive lock on a document. Returns 423 if already locked by another user."""
    doc = _get_doc_or_404(db, document_id, current_context.org_id)

    lock = db.query(DocumentLock).filter(DocumentLock.document_id == doc.id).first()

    if lock and not _is_lock_expired(lock):
        if lock.locked_by != current_context.user.id:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"Document is locked by another user until {lock.expires_at.isoformat()}"
            )
        # Re-acquiring own lock — extend TTL
        lock.expires_at = datetime.now(timezone.utc) + timedelta(minutes=body.ttl_minutes)
        lock.lock_reason = body.reason or lock.lock_reason
    else:
        if lock:
            db.delete(lock)
            db.flush()
        lock = DocumentLock(
            document_id=doc.id,
            locked_by=current_context.user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=body.ttl_minutes),
            lock_reason=body.reason,
        )
        db.add(lock)

    db.commit()
    db.refresh(lock)

    logger.info("[lock] Document %s locked by %s until %s", document_id, current_context.user.id, lock.expires_at)
    return LockResponse(
        document_id=document_id,
        locked=True,
        locked_by=str(lock.locked_by),
        locked_at=lock.locked_at,
        expires_at=lock.expires_at,
        lock_reason=lock.lock_reason,
        is_own_lock=True,
    )


@router.put("/documents/{document_id}/lock", response_model=LockResponse)
def renew_lock(
    document_id: str,
    body: LockRequest,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:lock")),
    db: Session = Depends(get_db),
) -> Any:
    """Extend TTL on your own lock."""
    doc = _get_doc_or_404(db, document_id, current_context.org_id)

    lock = db.query(DocumentLock).filter(DocumentLock.document_id == doc.id).first()
    if not lock or _is_lock_expired(lock):
        raise HTTPException(status_code=404, detail="No active lock on this document")
    if lock.locked_by != current_context.user.id:
        raise HTTPException(status_code=403, detail="You do not own this lock")

    lock.expires_at = datetime.now(timezone.utc) + timedelta(minutes=body.ttl_minutes)
    db.commit()
    db.refresh(lock)

    return LockResponse(
        document_id=document_id,
        locked=True,
        locked_by=str(lock.locked_by),
        locked_at=lock.locked_at,
        expires_at=lock.expires_at,
        lock_reason=lock.lock_reason,
        is_own_lock=True,
    )


@router.delete("/documents/{document_id}/lock", status_code=status.HTTP_204_NO_CONTENT)
def release_lock(
    document_id: str,
    current_context: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
):
    """Release a document lock. Lock owner or Org Admin only."""
    doc = _get_doc_or_404(db, document_id, current_context.org_id)

    lock = db.query(DocumentLock).filter(DocumentLock.document_id == doc.id).first()
    if not lock:
        raise HTTPException(status_code=404, detail="No active lock on this document")

    is_admin = current_context.role_name in ("Organization Admin", "Super Admin")
    if lock.locked_by != current_context.user.id and not is_admin:
        raise HTTPException(status_code=403, detail="You do not own this lock")

    db.delete(lock)
    db.commit()
    logger.info("[lock] Document %s lock released by %s", document_id, current_context.user.id)

"""
Sprint 11 - Approval Workflow API
POST /documents/{id}/approval/submit   - submit for review
GET  /documents/{id}/approval          - current approval state
POST /documents/{id}/approval/decide   - approve or reject (Approver role)
GET  /admin/approvals/pending          - list all pending approvals
"""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user_context, CurrentUserContext, get_db, PermissionChecker
from backend.app.models.models import ApprovalRequest, Document

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class ApprovalSubmitRequest(BaseModel):
    note: Optional[str] = None


class ApprovalDecideRequest(BaseModel):
    decision: str  # "approved" | "rejected"
    note: Optional[str] = None


class ApprovalResponse(BaseModel):
    id: str
    document_id: str
    status: str
    submitted_by: str
    reviewed_by: Optional[str]
    submission_note: Optional[str]
    review_note: Optional[str]
    submitted_at: datetime
    reviewed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_doc_or_404(db: Session, document_id: str, org_id: str) -> Document:
    doc = db.query(Document).filter(
        Document.id == uuid.UUID(document_id),
        Document.org_id == uuid.UUID(org_id),
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/documents/{document_id}/approval/submit", response_model=ApprovalResponse)
def submit_for_approval(
    document_id: str,
    body: ApprovalSubmitRequest,
    current_context: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> Any:
    """Submit a document for approval review."""
    doc = _get_doc_or_404(db, document_id, current_context.org_id)

    # Check for existing pending request
    existing = db.query(ApprovalRequest).filter(
        ApprovalRequest.document_id == doc.id,
        ApprovalRequest.status == "pending",
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Document already has a pending approval request")

    req = ApprovalRequest(
        document_id=doc.id,
        org_id=doc.org_id,
        submitted_by=current_context.user.id,
        status="pending",
        submission_note=body.note,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    logger.info("[approval] Document %s submitted for approval by %s", document_id, current_context.user.id)
    return ApprovalResponse(
        id=str(req.id),
        document_id=str(req.document_id),
        status=req.status,
        submitted_by=str(req.submitted_by),
        reviewed_by=str(req.reviewed_by) if req.reviewed_by else None,
        submission_note=req.submission_note,
        review_note=req.review_note,
        submitted_at=req.submitted_at,
        reviewed_at=req.reviewed_at,
    )


@router.get("/documents/{document_id}/approval", response_model=ApprovalResponse)
def get_approval_status(
    document_id: str,
    current_context: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db),
) -> Any:
    """Get the latest approval request for a document."""
    doc = _get_doc_or_404(db, document_id, current_context.org_id)

    req = db.query(ApprovalRequest).filter(
        ApprovalRequest.document_id == doc.id,
    ).order_by(ApprovalRequest.submitted_at.desc()).first()

    if not req:
        raise HTTPException(status_code=404, detail="No approval request found for this document")

    return ApprovalResponse(
        id=str(req.id),
        document_id=str(req.document_id),
        status=req.status,
        submitted_by=str(req.submitted_by),
        reviewed_by=str(req.reviewed_by) if req.reviewed_by else None,
        submission_note=req.submission_note,
        review_note=req.review_note,
        submitted_at=req.submitted_at,
        reviewed_at=req.reviewed_at,
    )


@router.post("/documents/{document_id}/approval/decide", response_model=ApprovalResponse)
def decide_approval(
    document_id: str,
    body: ApprovalDecideRequest,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:approve")),
    db: Session = Depends(get_db),
) -> Any:
    """Approve or reject a document. Requires 'documents:approve' permission (Approver role)."""
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'")

    doc = _get_doc_or_404(db, document_id, current_context.org_id)

    req = db.query(ApprovalRequest).filter(
        ApprovalRequest.document_id == doc.id,
        ApprovalRequest.status == "pending",
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="No pending approval request for this document")

    req.status = body.decision
    req.reviewed_by = current_context.user.id
    req.review_note = body.note
    req.reviewed_at = datetime.now(timezone.utc)

    # Update document status
    doc.status = body.decision  # "approved" | "rejected"
    db.commit()
    db.refresh(req)

    logger.info(
        "[approval] Document %s %s by %s", document_id, body.decision, current_context.user.id
    )
    return ApprovalResponse(
        id=str(req.id),
        document_id=str(req.document_id),
        status=req.status,
        submitted_by=str(req.submitted_by),
        reviewed_by=str(req.reviewed_by) if req.reviewed_by else None,
        submission_note=req.submission_note,
        review_note=req.review_note,
        submitted_at=req.submitted_at,
        reviewed_at=req.reviewed_at,
    )


@router.get("/approvals/pending")
def list_pending_approvals(
    limit: int = 50,
    offset: int = 0,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:approve")),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List all pending approval requests across the organization."""
    reqs = db.query(ApprovalRequest).filter(
        ApprovalRequest.org_id == uuid.UUID(current_context.org_id),
        ApprovalRequest.status == "pending",
    ).order_by(ApprovalRequest.submitted_at.asc()).offset(offset).limit(limit).all()

    return [
        {
            "id": str(r.id),
            "document_id": str(r.document_id),
            "submitted_by": str(r.submitted_by),
            "submission_note": r.submission_note,
            "submitted_at": r.submitted_at.isoformat(),
        }
        for r in reqs
    ]

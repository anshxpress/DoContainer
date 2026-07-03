import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.db import get_db
from backend.app.models.models import DocumentComment, Document
from backend.app.schemas.schemas import DocumentCommentCreate, DocumentCommentResponse
from backend.app.api.deps import get_current_user_context, CurrentUserContext, PermissionChecker

router = APIRouter(prefix="/documents", tags=["Comments"])

@router.get("/{doc_id}/comments", response_model=List[DocumentCommentResponse])
def get_comments(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read"))
):
    doc = db.query(Document).filter(Document.id == doc_id, Document.org_id == uuid.UUID(current_context.org_id)).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
        
    comments = db.query(DocumentComment).filter(DocumentComment.document_id == doc_id).order_by(DocumentComment.created_at.asc()).all()
    return comments

@router.post("/{doc_id}/comments", response_model=DocumentCommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(
    doc_id: uuid.UUID,
    comment_in: DocumentCommentCreate,
    db: Session = Depends(get_db),
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read"))
):
    doc = db.query(Document).filter(Document.id == doc_id, Document.org_id == uuid.UUID(current_context.org_id)).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    new_comment = DocumentComment(
        document_id=doc_id,
        user_id=uuid.UUID(current_context.user.id),
        parent_id=comment_in.parent_id,
        content=comment_in.content
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment

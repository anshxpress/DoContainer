import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.db import get_db
from backend.app.models.models import DocumentTask, Document, Notification
from backend.app.schemas.schemas import DocumentTaskCreate, DocumentTaskUpdate, DocumentTaskResponse
from backend.app.api.deps import get_current_user_context, CurrentUserContext, PermissionChecker

router = APIRouter(prefix="/tasks", tags=["Tasks"])
docs_router = APIRouter(prefix="/documents", tags=["Tasks"])

@router.get("", response_model=List[DocumentTaskResponse])
def get_user_tasks(
    task_status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read"))
):
    query = db.query(DocumentTask).filter(DocumentTask.assigned_to == uuid.UUID(current_context.user.id))
    if task_status:
        query = query.filter(DocumentTask.status == task_status)
    return query.order_by(DocumentTask.created_at.desc()).all()

@docs_router.post("/{doc_id}/tasks", response_model=DocumentTaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    doc_id: uuid.UUID,
    task_in: DocumentTaskCreate,
    db: Session = Depends(get_db),
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read"))
):
    doc = db.query(Document).filter(Document.id == doc_id, Document.org_id == uuid.UUID(current_context.org_id)).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    due_dt = datetime.fromisoformat(task_in.due_date) if task_in.due_date else None
    
    new_task = DocumentTask(
        document_id=doc_id,
        assigned_by=uuid.UUID(current_context.user.id),
        assigned_to=task_in.assigned_to,
        title=task_in.title,
        description=task_in.description,
        due_date=due_dt
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    
    # Create notification
    notif = Notification(
        user_id=new_task.assigned_to,
        org_id=uuid.UUID(current_context.org_id),
        message=f"You have been assigned a new task: {new_task.title}",
        notification_type="task",
        link=f"/dashboard/documents/{doc_id}?tab=tasks"
    )
    db.add(notif)
    db.commit()
    
    return new_task

@router.patch("/{task_id}", response_model=DocumentTaskResponse)
def update_task(
    task_id: uuid.UUID,
    task_in: DocumentTaskUpdate,
    db: Session = Depends(get_db),
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read"))
):
    task = db.query(DocumentTask).filter(
        DocumentTask.id == task_id, 
        DocumentTask.assigned_to == uuid.UUID(current_context.user.id)
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or not assigned to you")

    if task_in.status:
        task.status = task_in.status
    if task_in.title:
        task.title = task_in.title
    if task_in.description is not None:
        task.description = task_in.description
    if task_in.due_date:
        task.due_date = datetime.fromisoformat(task_in.due_date)
        
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

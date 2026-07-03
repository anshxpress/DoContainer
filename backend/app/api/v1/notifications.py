import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.db import get_db
from backend.app.models.models import Notification
from backend.app.schemas.schemas import NotificationResponse, NotificationUpdate
from backend.app.api.deps import get_current_user_context, CurrentUserContext, PermissionChecker

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("", response_model=List[NotificationResponse])
def get_user_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read"))
):
    query = db.query(Notification).filter(Notification.user_id == uuid.UUID(current_context.user.id))
    if unread_only:
        query = query.filter(Notification.is_read == False)
    return query.order_by(Notification.created_at.desc()).all()

@router.patch("/{notif_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notif_id: uuid.UUID,
    notif_in: NotificationUpdate,
    db: Session = Depends(get_db),
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read"))
):
    notif = db.query(Notification).filter(
        Notification.id == notif_id,
        Notification.user_id == uuid.UUID(current_context.user.id)
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = notif_in.is_read
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif

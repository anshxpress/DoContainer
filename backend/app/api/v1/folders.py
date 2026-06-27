import uuid
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.api.deps import get_current_user_context, CurrentUserContext, PermissionChecker
from backend.app.core.db import get_db
from backend.app.models.models import Folder, Document

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Pydantic Schemas ---

class FolderResponse(BaseModel):
    id: uuid.UUID
    parent_id: Optional[uuid.UUID]
    org_id: uuid.UUID
    team_id: Optional[uuid.UUID]
    name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[uuid.UUID] = None
    team_id: Optional[uuid.UUID] = None

class FolderUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None

# --- Endpoints ---

@router.get("", response_model=List[FolderResponse])
def list_folders(
    parent_id: Optional[str] = None,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/folders
    Lists all folders in the organization, optionally filtered by parent_id.
    """
    query = db.query(Folder).filter(Folder.org_id == uuid.UUID(current_context.org_id))
    
    if parent_id is not None:
        if parent_id.lower() == "root":
            query = query.filter(Folder.parent_id == None)
        else:
            try:
                query = query.filter(Folder.parent_id == uuid.UUID(parent_id))
            except ValueError:
                pass
                
    return query.order_by(Folder.name.asc()).all()

@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(
    payload: FolderCreate,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:write")),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/folders
    Creates a new folder.
    """
    org_id = uuid.UUID(current_context.org_id)
    
    if payload.parent_id:
        parent = db.query(Folder).filter(Folder.id == payload.parent_id, Folder.org_id == org_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent folder not found.")
            
    folder = Folder(
        id=uuid.uuid4(),
        org_id=org_id,
        name=payload.name,
        parent_id=payload.parent_id,
        team_id=payload.team_id
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder

@router.patch("/{folder_id}", response_model=FolderResponse)
def update_folder(
    folder_id: uuid.UUID,
    payload: FolderUpdate,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:write")),
    db: Session = Depends(get_db)
):
    """
    PATCH /api/v1/folders/{folder_id}
    Rename or move a folder.
    """
    org_id = uuid.UUID(current_context.org_id)
    folder = db.query(Folder).filter(Folder.id == folder_id, Folder.org_id == org_id).first()
    
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found.")
        
    if payload.name is not None:
        folder.name = payload.name
        
    if payload.parent_id is not None:
        if payload.parent_id == folder_id:
            raise HTTPException(status_code=400, detail="Folder cannot be its own parent.")
        folder.parent_id = payload.parent_id
        
    db.commit()
    db.refresh(folder)
    return folder

@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: uuid.UUID,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:write")),
    db: Session = Depends(get_db)
):
    """
    DELETE /api/v1/folders/{folder_id}
    Deletes a folder. Currently requires the folder to be empty (no subfolders, no documents).
    """
    org_id = uuid.UUID(current_context.org_id)
    folder = db.query(Folder).filter(Folder.id == folder_id, Folder.org_id == org_id).first()
    
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found.")
        
    # Check if empty
    has_subfolders = db.query(Folder).filter(Folder.parent_id == folder_id).first() is not None
    if has_subfolders:
        raise HTTPException(status_code=400, detail="Cannot delete folder with subfolders.")
        
    has_docs = db.query(Document).filter(Document.folder_id == folder_id).first() is not None
    if has_docs:
        raise HTTPException(status_code=400, detail="Cannot delete folder containing documents.")
        
    db.delete(folder)
    db.commit()
    return None

from typing import List, Optional
from sqlalchemy.orm import Session
import uuid
from backend.app.repositories.base_repo import document_repo, Document
from backend.app.api.deps import CurrentUserContext

class DocumentService:
    def get_document_list(self, db: Session, current_context: CurrentUserContext, folder_id: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Document]:
        query = db.query(document_repo.model).filter(document_repo.model.org_id == uuid.UUID(current_context.org_id))
        if folder_id:
            if folder_id.lower() == "root":
                query = query.filter(document_repo.model.folder_id == None)
            else:
                try:
                    query = query.filter(document_repo.model.folder_id == uuid.UUID(folder_id))
                except ValueError:
                    pass
        
        query = query.order_by(document_repo.model.created_at.desc())
        return query.offset(skip).limit(limit).all()

    def get_processing_documents(self, db: Session, current_context: CurrentUserContext) -> List[Document]:
        return db.query(document_repo.model).filter(
            document_repo.model.org_id == uuid.UUID(current_context.org_id),
            document_repo.model.status.in_(["queued", "processing", "failed"])
        ).order_by(document_repo.model.created_at.desc()).all()

document_service = DocumentService()

from typing import Generic, TypeVar, Type, List, Optional, Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from backend.app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        return db.query(self.model).filter(self.model.id == id).first()

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[ModelType]:
        return db.query(self.model).offset(skip).limit(limit).all()

    def create(self, db: Session, *, obj_in: Dict[str, Any]) -> ModelType:
        db_obj = self.model(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, *, db_obj: ModelType, obj_in: Dict[str, Any]) -> ModelType:
        for field in obj_in:
            if hasattr(db_obj, field):
                setattr(db_obj, field, obj_in[field])
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: Any) -> Optional[ModelType]:
        obj = db.query(self.model).get(id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj


from backend.app.models.models import User, Organization, Team, Department, Role, Permission, Membership, TeamMembership, Folder, Document, DocumentPage, SearchLog, AuditLog, UsageMetric

class UserRepository(BaseRepository[User]):
    def __init__(self):
        super().__init__(User)

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

class OrganizationRepository(BaseRepository[Organization]):
    def __init__(self):
        super().__init__(Organization)

    def get_by_domain(self, db: Session, domain: str) -> Optional[Organization]:
        return db.query(Organization).filter(Organization.domain == domain).first()

class DepartmentRepository(BaseRepository[Department]):
    def __init__(self):
        super().__init__(Department)

class TeamRepository(BaseRepository[Team]):
    def __init__(self):
        super().__init__(Team)

class RoleRepository(BaseRepository[Role]):
    def __init__(self):
        super().__init__(Role)

    def get_by_name(self, db: Session, org_id: Optional[Any], name: str) -> Optional[Role]:
        return db.query(Role).filter(Role.org_id == org_id, Role.name == name).first()

class PermissionRepository(BaseRepository[Permission]):
    def __init__(self):
        super().__init__(Permission)

    def get_by_name(self, db: Session, name: str) -> Optional[Permission]:
        return db.query(Permission).filter(Permission.name == name).first()

class MembershipRepository(BaseRepository[Membership]):
    def __init__(self):
        super().__init__(Membership)

    def get_by_user_and_org(self, db: Session, user_id: Any, org_id: Any) -> Optional[Membership]:
        return db.query(Membership).filter(Membership.user_id == user_id, Membership.org_id == org_id).first()

class FolderRepository(BaseRepository[Folder]):
    def __init__(self):
        super().__init__(Folder)

    def get_by_org(self, db: Session, org_id: Any) -> List[Folder]:
        return db.query(Folder).filter(Folder.org_id == org_id).all()

    def get_subfolders(self, db: Session, parent_id: Any) -> List[Folder]:
        return db.query(Folder).filter(Folder.parent_id == parent_id).all()

class TeamMembershipRepository:
    # Since TeamMembership has composite primary key, we manage it manually without simple BaseRepository
    def get(self, db: Session, team_id: Any, user_id: Any) -> Optional[TeamMembership]:
        return db.query(TeamMembership).filter(
            TeamMembership.team_id == team_id,
            TeamMembership.user_id == user_id
        ).first()

    def create(self, db: Session, *, obj_in: Dict[str, Any]) -> TeamMembership:
        db_obj = TeamMembership(**obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, team_id: Any, user_id: Any) -> Optional[TeamMembership]:
        obj = self.get(db, team_id, user_id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj


class DocumentRepository(BaseRepository[Document]):
    def __init__(self):
        super().__init__(Document)

    def get_by_org(self, db: Session, org_id: Any) -> List[Document]:
        return db.query(Document).filter(Document.org_id == org_id).all()

    def update_status(self, db: Session, doc_id: Any, status: str, error_message: Optional[str] = None) -> Optional[Document]:
        doc = self.get(db, doc_id)
        if doc:
            doc.status = status
            doc.error_message = error_message
            db.add(doc)
            db.commit()
            db.refresh(doc)
        return doc

class DocumentPageRepository(BaseRepository[DocumentPage]):
    def __init__(self):
        super().__init__(DocumentPage)

    def get_by_document(self, db: Session, document_id: Any) -> List[DocumentPage]:
        return db.query(DocumentPage).filter(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number).all()

    def search_pages_fts(
        self,
        db: Session,
        org_id: str,
        team_ids: List[str],
        query_text: str,
        folder_id: Optional[str] = None,
        document_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[DocumentPage]:
        """
        Day 4: PostgreSQL Full-Text Search fallback.
        """
        ts_query = func.websearch_to_tsquery("english", query_text)
        ts_rank_expr = func.ts_rank(
            func.to_tsvector("english", func.coalesce(DocumentPage.text_content, "")),
            ts_query,
        )

        q = (
            db.query(DocumentPage)
            .join(Document, Document.id == DocumentPage.document_id)
            .filter(
                Document.org_id == org_id,
                func.to_tsvector("english", func.coalesce(DocumentPage.text_content, "")).op("@@")(ts_query),
            )
        )

        # Optional folder scope
        if folder_id:
            q = q.filter(Document.folder_id == folder_id)
            
        # Optional document scope
        if document_id:
            q = q.filter(Document.id == document_id)

        # Team-level access control
        # e.g. org admins with no team restrictions)
        if team_ids:
            from backend.app.models.models import Folder as FolderModel
            q = q.join(FolderModel, FolderModel.id == Document.folder_id, isouter=True)
            q = q.filter(
                (FolderModel.team_id.is_(None)) |
                (FolderModel.team_id.in_(team_ids))
            )

        return (
            q.order_by(ts_rank_expr.desc())
            .limit(limit)
            .all()
        )


user_repo = UserRepository()
org_repo = OrganizationRepository()
dept_repo = DepartmentRepository()
team_repo = TeamRepository()
role_repo = RoleRepository()
permission_repo = PermissionRepository()
membership_repo = MembershipRepository()
team_membership_repo = TeamMembershipRepository()
folder_repo = FolderRepository()
document_repo = DocumentRepository()
document_page_repo = DocumentPageRepository()


class SearchLogRepository(BaseRepository[SearchLog]):
    def __init__(self):
        super().__init__(SearchLog)


search_log_repo = SearchLogRepository()


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self):
        super().__init__(AuditLog)


class UsageMetricRepository(BaseRepository[UsageMetric]):
    def __init__(self):
        super().__init__(UsageMetric)


audit_log_repo = AuditLogRepository()
usage_metric_repo = UsageMetricRepository()

from backend.app.models.models import ApprovalRequest, DocumentLock, DocumentACL, RetentionPolicy

class ApprovalRequestRepository(BaseRepository[ApprovalRequest]):
    def __init__(self):
        super().__init__(ApprovalRequest)

class DocumentLockRepository(BaseRepository[DocumentLock]):
    def __init__(self):
        super().__init__(DocumentLock)
        
class DocumentAclRepository(BaseRepository[DocumentACL]):
    def __init__(self):
        super().__init__(DocumentACL)
        
class RetentionPolicyRepository(BaseRepository[RetentionPolicy]):
    def __init__(self):
        super().__init__(RetentionPolicy)

approval_request_repo = ApprovalRequestRepository()
document_lock_repo = DocumentLockRepository()
document_acl_repo = DocumentAclRepository()
retention_policy_repo = RetentionPolicyRepository()

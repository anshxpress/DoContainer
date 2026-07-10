from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Generator
from backend.app.core.db import get_db
from backend.app.core.security import decode_token, RSA_PUBLIC_KEY
from backend.app.core.config import settings
from backend.app.models.models import User, Membership, Role, Permission

reusable_oauth2 = HTTPBearer()

class CurrentUserContext:
    def __init__(self, user: User, org_id: str, role_name: str, permissions: List[str]):
        self.user = user
        self.org_id = org_id
        self.role_name = role_name
        self.permissions = permissions


def get_current_user_context(
    token_credentials: HTTPAuthorizationCredentials = Depends(reusable_oauth2),
    db: Session = Depends(get_db)
) -> CurrentUserContext:
    token = token_credentials.credentials
    payload = decode_token(token)
    
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing subject claim",
        )

    # Convert the JWT `sub` claim (string) to a UUID object for SQLAlchemy / SQLite compatibility
    try:
        import uuid as _uuid
        user_uuid = _uuid.UUID(str(user_id))
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identifier in token",
        )

    # Get user
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    # Get organization membership (default to first active membership)
    membership = db.query(Membership).filter(Membership.user_id == user.id).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of any organization"
        )

    # Get role and its permissions
    role = membership.role
    permissions = [p.name for p in role.permissions]

    return CurrentUserContext(
        user=user,
        org_id=str(membership.org_id),
        role_name=role.name,
        permissions=permissions
    )


class PermissionChecker:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    def __call__(
        self,
        current_context: CurrentUserContext = Depends(get_current_user_context)
    ) -> CurrentUserContext:
        # Super Admin and Organization Admin have all permissions
        if current_context.role_name in ("Super Admin", "Organization Admin"):
            return current_context
            
        if self.required_permission not in current_context.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {self.required_permission}"
            )
        return current_context


def get_db() -> Generator:
    """FastAPI dependency: yields a SQLAlchemy session."""
    from backend.app.core.db import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_document_permission(
    db: Session,
    document_id: str,
    current_context: "CurrentUserContext",
    permission: str,
) -> bool:
    """
    Returns True if the user has *permission* for the given document, evaluated as:
      1. Org Admin / Super Admin -> always True
      2. Personal mode (ACL disabled) -> True if document belongs to user's org
      3. Org-level RBAC permission present -> True
      4. Document-level ACL entry -> True
      5. Otherwise -> False

    Callers should raise HTTP 403 if False.
    """
    import uuid as _uuid
    from backend.app.core.config import features

    # Admins bypass everything
    if current_context.role_name in ("Super Admin", "Organization Admin"):
        return True

    # ── Personal mode shortcircuit ──────────────────────────────────────────
    # In Personal mode, ACL / team-based checks are disabled.
    # Grant access if the document belongs to the user's organisation.
    if not features.ENABLE_ACL:
        from backend.app.models.models import Document
        doc_uuid = _uuid.UUID(str(document_id))
        doc = db.query(Document).filter(Document.id == doc_uuid).first()
        if doc and str(doc.org_id) == current_context.org_id:
            return True
        return False

    # Org-level permission check
    if permission in current_context.permissions:
        return True

    # Document ACL check
    from backend.app.models.models import DocumentACL, TeamMembership
    doc_uuid = _uuid.UUID(str(document_id))
    user_uuid = current_context.user.id

    # Collect teams the user belongs to
    team_rows = db.query(TeamMembership.team_id).filter(
        TeamMembership.user_id == user_uuid
    ).all()
    team_ids = [str(r.team_id) for r in team_rows]

    # Get role id
    membership = db.query(Membership).filter(Membership.user_id == user_uuid).first()
    role_id = membership.role_id if membership else None

    from backend.app.services.security_service import check_document_acl
    return check_document_acl(
        db=db,
        document_id=doc_uuid,
        user_id=user_uuid,
        permission=permission,
        user_team_ids=team_ids,
        user_role_id=role_id,
    )



def get_document_or_404(db: Session, document_id: str, org_id: str):
    import uuid
    from backend.app.models.models import Document
    try:
        doc_uuid = uuid.UUID(str(document_id))
        org_uuid = uuid.UUID(str(org_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
        
    doc = db.query(Document).filter(
        Document.id == doc_uuid,
        Document.org_id == org_uuid
    ).first()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

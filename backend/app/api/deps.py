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

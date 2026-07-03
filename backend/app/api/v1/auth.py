from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from sqlalchemy.orm import Session
import uuid
from backend.app.core.db import get_db
from backend.app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from backend.app.schemas.schemas import UserCreate, UserLogin, Token, UserResponse, OrganizationResponse, UserProfileResponse
from backend.app.services.auth_service import auth_service
from backend.app.repositories.base_repo import user_repo, org_repo, role_repo, membership_repo
from backend.app.models.models import Role, Membership, Organization, Permission
from backend.app.api.deps import get_current_user_context, CurrentUserContext



router = APIRouter()

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, response: Response, db: Session = Depends(get_db)):
    db_user, db_org, role_name, access_token, refresh_token = auth_service.register_user(db, user_in)

    # 6. Set HTTP-Only Cookie for Refresh Token
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,  # In prod this is true. For local dev, modern browsers support it if localhost
        samesite="lax",
        max_age=7 * 24 * 3600  # 7 days
    )

    return Token(
        access_token=access_token,
        user=UserResponse.model_validate(db_user),
        organization=OrganizationResponse.model_validate(db_org),
        role=role_name
    )


@router.post("/login", response_model=Token)
def login(user_in: UserLogin, response: Response, db: Session = Depends(get_db)):
    db_user, db_org, role_name, access_token, refresh_token = auth_service.login_user(db, user_in)

    # 4. Set HTTP-Only Cookie for Refresh Token
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 3600
    )

    return Token(
        access_token=access_token,
        user=UserResponse.model_validate(db_user),
        organization=OrganizationResponse.model_validate(db_org),
        role=role_name
    )


@router.get("/me", response_model=UserProfileResponse)
def get_me(
    current_context: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/auth/me
    Retrieves the profile of the current authenticated user.
    """
    db_user = current_context.user
    db_org = db.query(Organization).filter(Organization.id == uuid.UUID(current_context.org_id)).first()
    org_name = db_org.name if db_org else "Docscope Inc"

    return UserProfileResponse(
        id=db_user.id,
        email=db_user.email,
        first_name=db_user.first_name,
        last_name=db_user.last_name,
        organization_name=org_name,
        role=current_context.role_name
    )


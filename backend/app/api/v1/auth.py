from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from sqlalchemy.orm import Session
import uuid
from backend.app.core.db import get_db
from backend.app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token
from backend.app.schemas.schemas import UserCreate, UserLogin, Token, UserResponse, OrganizationResponse, UserProfileResponse
from backend.app.repositories.base_repo import user_repo, org_repo, role_repo, membership_repo
from backend.app.models.models import Role, Membership, Organization, Permission
from backend.app.api.deps import get_current_user_context, CurrentUserContext



router = APIRouter()

@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, response: Response, db: Session = Depends(get_db)):
    # Check if user already exists
    db_user = user_repo.get_by_email(db, email=user_in.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists."
        )

    # 1. Create Organization
    org_data = {"name": user_in.org_name}
    db_org = org_repo.create(db, obj_in=org_data)

    # 2. Ensure default roles exist for this organization
    default_roles = ["Organization Admin", "Manager", "Analyst", "Viewer", "Guest"]
    roles_map = {}
    for role_name in default_roles:
        db_role = role_repo.get_by_name(db, org_id=db_org.id, name=role_name)
        if not db_role:
            db_role = role_repo.create(db, obj_in={
                "org_id": db_org.id,
                "name": role_name,
                "description": f"Default {role_name} role for organization."
            })
        roles_map[role_name] = db_role

    # Ensure system permissions exist in the database and link them to roles
    system_permissions = [
        ("documents:read", "Read document metadata and statuses."),
        ("documents:write", "Upload, edit, and delete documents."),
        ("search:documents", "Perform hybrid search and AI chat prompts."),
        ("analytics:read", "View analytics charts and security audit logs."),
        ("manage:users", "Manage users within the organization."),
        ("manage:teams", "Create and manage teams."),
        ("manage:roles", "View and modify role permissions."),
    ]
    
    permissions_map = {}
    for perm_name, perm_desc in system_permissions:
        db_perm = db.query(Permission).filter(Permission.name == perm_name).first()
        if not db_perm:
            db_perm = Permission(name=perm_name, description=perm_desc)
            db.add(db_perm)
            db.flush()
        permissions_map[perm_name] = db_perm

    # For each role, assign default permissions
    org_admin_role = roles_map["Organization Admin"]
    org_admin_role.permissions = list(permissions_map.values())
    db.add(org_admin_role)

    manager_role = roles_map["Manager"]
    manager_role.permissions = [permissions_map["documents:read"], permissions_map["documents:write"], permissions_map["search:documents"]]
    db.add(manager_role)

    analyst_role = roles_map["Analyst"]
    analyst_role.permissions = [permissions_map["documents:read"], permissions_map["search:documents"], permissions_map["analytics:read"]]
    db.add(analyst_role)

    viewer_role = roles_map["Viewer"]
    viewer_role.permissions = [permissions_map["documents:read"], permissions_map["search:documents"]]
    db.add(viewer_role)
    db.flush()


    # 3. Create User
    password_hash = get_password_hash(user_in.password)
    user_data = {
        "email": user_in.email,
        "password_hash": password_hash,
        "first_name": user_in.first_name,
        "last_name": user_in.last_name,
        "is_active": True
    }
    db_user = user_repo.create(db, obj_in=user_data)

    # 4. Create Membership linking User to Org as Organization Admin
    org_admin_role = roles_map["Organization Admin"]
    membership_data = {
        "user_id": db_user.id,
        "org_id": db_org.id,
        "role_id": org_admin_role.id
    }
    membership_repo.create(db, obj_in=membership_data)

    # 5. Generate Tokens
    access_token = create_access_token(subject=db_user.id)
    refresh_token = create_refresh_token(subject=db_user.id)

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
        role="Organization Admin"
    )


@router.post("/login", response_model=Token)
def login(user_in: UserLogin, response: Response, db: Session = Depends(get_db)):
    # 1. Authenticate user
    db_user = user_repo.get_by_email(db, email=user_in.email)
    if not db_user or not verify_password(user_in.password, db_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password."
        )

    if not db_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account."
        )

    # 2. Get User Organization Membership
    # Note: For simplicity in the initial MVP, we fetch the first membership
    membership = db.query(Membership).filter(Membership.user_id == db_user.id).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to any organization."
        )

    db_org = membership.organization
    db_role = membership.role

    # 3. Generate Tokens
    access_token = create_access_token(subject=db_user.id)
    refresh_token = create_refresh_token(subject=db_user.id)

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
        role=db_role.name
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


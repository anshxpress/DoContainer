from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from backend.app.schemas.schemas import UserCreate, UserLogin
from backend.app.repositories.base_repo import user_repo, org_repo, role_repo, membership_repo
from backend.app.models.models import Permission, Membership
from backend.app.core.security import verify_password, get_password_hash, create_access_token, create_refresh_token

class AuthService:
    def register_user(self, db: Session, user_in: UserCreate):
        db_user = user_repo.get_by_email(db, email=user_in.email)
        if db_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email already exists."
            )

        org_name_to_use = user_in.org_name
        if not org_name_to_use:
            first = user_in.first_name or "Personal"
            org_name_to_use = f"{first}'s Workspace"
            
        org_data = {"name": org_name_to_use}
        db_org = org_repo.create(db, obj_in=org_data)

        default_roles = ["Organization Admin", "Manager", "Analyst", "Viewer", "Guest", "Approver"]
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

        system_permissions = [
            ("documents:read", "Read document metadata and statuses."),
            ("documents:write", "Upload, edit, and delete documents."),
            ("search:documents", "Perform hybrid search and AI chat prompts."),
            ("analytics:read", "View analytics charts and security audit logs."),
            ("manage:users", "Manage users within the organization."),
            ("manage:teams", "Create and manage teams."),
            ("manage:roles", "View and modify role permissions."),
            ("documents:version", "View and upload document versions."),
            ("documents:approve", "Approve or reject documents in approval workflow."),
            ("documents:lock", "Acquire and release document locks."),
            ("documents:acl:manage", "Grant and revoke per-document ACL entries."),
            ("documents:download:signed", "Generate signed download URLs."),
            ("manage:retention", "Create and manage data retention policies."),
        ]
        
        permissions_map = {}
        for perm_name, perm_desc in system_permissions:
            db_perm = db.query(Permission).filter(Permission.name == perm_name).first()
            if not db_perm:
                db_perm = Permission(name=perm_name, description=perm_desc)
                db.add(db_perm)
                db.flush()
            permissions_map[perm_name] = db_perm

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

        approver_role = roles_map["Approver"]
        approver_role.permissions = [
            permissions_map["documents:read"],
            permissions_map["documents:approve"],
            permissions_map["documents:version"],
            permissions_map["documents:download:signed"],
        ]
        db.add(approver_role)
        db.flush()

        password_hash = get_password_hash(user_in.password)
        user_data = {
            "email": user_in.email,
            "password_hash": password_hash,
            "first_name": user_in.first_name,
            "last_name": user_in.last_name,
            "is_active": True
        }
        db_user = user_repo.create(db, obj_in=user_data)

        membership_data = {
            "user_id": db_user.id,
            "org_id": db_org.id,
            "role_id": org_admin_role.id
        }
        membership_repo.create(db, obj_in=membership_data)

        access_token = create_access_token(subject=db_user.id)
        refresh_token = create_refresh_token(subject=db_user.id)

        return db_user, db_org, org_admin_role.name, access_token, refresh_token

    def login_user(self, db: Session, user_in: UserLogin):
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

        membership = db.query(Membership).filter(Membership.user_id == db_user.id).first()
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User does not belong to any organization."
            )

        access_token = create_access_token(subject=db_user.id)
        refresh_token = create_refresh_token(subject=db_user.id)

        return db_user, membership.organization, membership.role.name, access_token, refresh_token

auth_service = AuthService()

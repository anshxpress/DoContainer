import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
import uuid
from datetime import datetime

from backend.app.api.deps import get_current_user_context, CurrentUserContext, PermissionChecker
from backend.app.core.db import get_db
from backend.app.models.models import User, Organization, Membership, Role, Team, TeamMembership, Permission, Folder

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Response Schemas ---

class AdminUserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    team: str
    status: str
    initials: str
    joined: str

class AdminTeamResponse(BaseModel):
    id: str
    name: str
    members: int
    folders: int
    acl: str

class AdminPermissionResponse(BaseModel):
    action: str
    desc: str
    roles: Dict[str, bool]

# --- Endpoints ---

@router.get("/users", response_model=List[AdminUserResponse])
def get_admin_users(
    current_context: CurrentUserContext = Depends(PermissionChecker("manage:users")),
    db: Session = Depends(get_db)
):
    """
    Fetch all users within the organization, including their roles and teams.
    """
    org_id = uuid.UUID(current_context.org_id)
    
    # Get all memberships for the org
    memberships = db.query(Membership).filter(Membership.org_id == org_id).all()
    
    result = []
    for m in memberships:
        user = m.user
        role = m.role.name if m.role else "Unknown"
        
        # Get team for user in this org
        team_name = "Unassigned"
        team_membership = db.query(TeamMembership).join(Team).filter(
            TeamMembership.user_id == user.id,
            Team.org_id == org_id
        ).first()
        
        if team_membership:
            team_name = team_membership.team.name
            
        # Build Name & Initials
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown User"
        initials = "".join([n[0].upper() for n in name.split()[:2]]) if name else "U"
        
        # Build Joined date
        joined = user.created_at.strftime("%b %d, %Y") if user.created_at else "Unknown"
        
        result.append(AdminUserResponse(
            id=str(user.id),
            name=name,
            email=user.email,
            role=role,
            team=team_name,
            status="active" if user.is_active else "inactive",
            initials=initials,
            joined=joined
        ))
        
    return result

@router.get("/teams", response_model=List[AdminTeamResponse])
def get_admin_teams(
    current_context: CurrentUserContext = Depends(PermissionChecker("manage:teams")),
    db: Session = Depends(get_db)
):
    """
    Fetch all teams within the organization.
    """
    org_id = uuid.UUID(current_context.org_id)
    teams = db.query(Team).filter(Team.org_id == org_id).all()
    
    result = []
    for team in teams:
        members_count = db.query(func.count(TeamMembership.user_id)).filter(TeamMembership.team_id == team.id).scalar()
        folders_count = db.query(func.count(Folder.id)).filter(Folder.team_id == team.id).scalar()
        
        result.append(AdminTeamResponse(
            id=str(team.id),
            name=team.name,
            members=members_count or 0,
            folders=folders_count or 0,
            acl="Read + Write" # Placeholder for team-level ACL logic
        ))
        
    return result

@router.get("/roles", response_model=List[AdminPermissionResponse])
def get_admin_roles_and_permissions(
    current_context: CurrentUserContext = Depends(PermissionChecker("manage:roles")),
    db: Session = Depends(get_db)
):
    """
    Fetch all permissions and the roles that have them.
    Builds a matrix matching the UI layout.
    """
    org_id = uuid.UUID(current_context.org_id)
    
    # We want system roles and org-specific roles
    roles = db.query(Role).filter((Role.org_id == None) | (Role.org_id == org_id)).all()
    
    # All system permissions
    permissions = db.query(Permission).all()
    
    result = []
    for perm in permissions:
        # Build roles dict: { "Org Admin": True, "Team Admin": False ... }
        roles_dict = {}
        for r in roles:
            has_perm = db.query(Permission).join(Role.permissions).filter(
                Role.id == r.id, 
                Permission.id == perm.id
            ).first() is not None
            roles_dict[r.name] = has_perm
            
        result.append(AdminPermissionResponse(
            action=perm.name,
            desc=perm.description or perm.name,
            roles=roles_dict
        ))
        
    return result

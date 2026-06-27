import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, ForeignKey, Boolean, DateTime, Text, UniqueConstraint, Table, Column, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from backend.app.models.base import Base

# Association table for Role-Permission link
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
)

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    departments: Mapped[List["Department"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    teams: Mapped[List["Team"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    roles: Mapped[List["Role"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    memberships: Mapped[List["Membership"]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="departments")
    teams: Mapped[List["Team"]] = relationship(back_populates="department")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    dept_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="teams")
    department: Mapped[Optional["Department"]] = relationship(back_populates="teams")
    memberships: Mapped[List["TeamMembership"]] = relationship(back_populates="team", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    memberships: Mapped[List["Membership"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    team_memberships: Mapped[List["TeamMembership"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    roles: Mapped[List["Role"]] = relationship(secondary=role_permissions, back_populates="permissions")


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    organization: Mapped[Optional["Organization"]] = relationship(back_populates="roles")
    permissions: Mapped[List["Permission"]] = relationship(secondary=role_permissions, back_populates="roles")

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="unique_org_role_name"),
    )


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship(back_populates="memberships")
    organization: Mapped["Organization"] = relationship(back_populates="memberships")
    role: Mapped["Role"] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "org_id", name="unique_user_org"),
        UniqueConstraint("user_id", "org_id", name="unique_memberships_user_org"), # ensuring double check compatibility
    )


class TeamMembership(Base):
    __tablename__ = "team_memberships"

    team_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    team: Mapped["Team"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(back_populates="team_memberships")
    role: Mapped[Optional["Role"]] = relationship()


class Folder(Base):
    __tablename__ = "folders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("folders.id", ondelete="CASCADE"), nullable=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    parent: Mapped[Optional["Folder"]] = relationship(back_populates="subfolders", remote_side=[id])
    subfolders: Mapped[List["Folder"]] = relationship(back_populates="parent", cascade="all, delete-orphan")
    organization: Mapped["Organization"] = relationship()
    team: Mapped[Optional["Team"]] = relationship()


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("folders.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued") # queued, processing, completed, failed
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    organization: Mapped["Organization"] = relationship()
    folder: Mapped[Optional["Folder"]] = relationship()
    pages: Mapped[List["DocumentPage"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(nullable=False)
    png_storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    qdrant_point_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    # Day 4: Stores extracted text for PostgreSQL full-text search fallback
    text_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="pages")


class SearchLog(Base):
    """
    Day 10: Search Telemetry Logging.
    Records every search request with timing and result metadata
    for analytics and performance monitoring.
    """
    __tablename__ = "search_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    org_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    result_count: Mapped[int] = mapped_column(nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user: Mapped[Optional["User"]] = relationship()


# ─────────────────────────────────────────────────────────────────────────────
# Sprint 4 — Day 4: Chat History Models
# ─────────────────────────────────────────────────────────────────────────────

class ChatSession(Base):
    """
    A named conversation session scoped to a user + organization.
    Groups a sequence of ChatMessage records.
    """
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="New Chat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship()
    messages: Mapped[List["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    """
    A single turn in a ChatSession.
    role = 'user' | 'assistant'
    citations_json = JSON-serialised list of {doc_name, page_number} dicts
    """
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)      # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session: Mapped["ChatSession"] = relationship(back_populates="messages")


# ─────────────────────────────────────────────────────────────────────────────
# Sprint 5 — Day 1: Telemetry and Partitioned Models
# ─────────────────────────────────────────────────────────────────────────────

class AuditLog(Base):
    """
    Audit log table partitioned by range on created_at.
    """
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, server_default=func.uuid_generate_v4())
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    resource: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[Optional["User"]] = relationship()
    organization: Mapped[Optional["Organization"]] = relationship()

    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at"),
        {"postgresql_partition_by": "RANGE (created_at)"}
    )


class UsageMetric(Base):
    """
    Usage metrics table partitioned by range on created_at.
    Tracks API tokens, storage bytes, and pages rendered.
    """
    __tablename__ = "usage_metrics"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, server_default=func.uuid_generate_v4())
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    metric_type: Mapped[str] = mapped_column(String(100), nullable=False)  # "pages_rendered", "storage_bytes", "api_tokens"
    value: Mapped[float] = mapped_column(nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped["Organization"] = relationship()

    __table_args__ = (
        PrimaryKeyConstraint("id", "created_at"),
        {"postgresql_partition_by": "RANGE (created_at)"}
    )


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
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Hybrid Pipeline: metadata enrichment fields
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships (existing)
    organization: Mapped["Organization"] = relationship()
    folder: Mapped[Optional["Folder"]] = relationship()
    pages: Mapped[List["DocumentPage"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    # Relationships (Hybrid Pipeline — NEW)
    parse_elements: Mapped[List["DocumentParseElement"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    ocr_chunks: Mapped[List["OcrChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    text_embedding_chunks: Mapped[List["TextEmbeddingChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    summary: Mapped[Optional["DocumentSummary"]] = relationship(back_populates="document", uselist=False, cascade="all, delete-orphan")
    keywords: Mapped[List["DocumentKeyword"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    entities: Mapped[List["DocumentEntity"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    processing_jobs: Mapped[List["ProcessingJob"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    processing_metrics: Mapped[List["ProcessingMetrics"]] = relationship(back_populates="document", cascade="all, delete-orphan")



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


# ─────────────────────────────────────────────────────────────────────────────
# Hybrid Pipeline — Docling Structural Elements
# ─────────────────────────────────────────────────────────────────────────────

class DocumentParseElement(Base):
    """
    Stores the structured elements extracted by Docling from each document.
    Preserves reading order, bounding boxes, and element type (heading,
    paragraph, table, image, figure, caption, list, header, footer).
    """
    __tablename__ = "document_parse_elements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(nullable=False)
    element_type: Mapped[str] = mapped_column(String(50), nullable=False)  # heading/paragraph/table/image/figure/list/caption/header/footer
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reading_order: Mapped[int] = mapped_column(nullable=False, default=0)
    # Normalized bounding box (0.0 – 1.0 relative to page dimensions)
    bbox_x0: Mapped[Optional[float]] = mapped_column(nullable=True)
    bbox_y0: Mapped[Optional[float]] = mapped_column(nullable=True)
    bbox_x1: Mapped[Optional[float]] = mapped_column(nullable=True)
    bbox_y1: Mapped[Optional[float]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="parse_elements")


# ─────────────────────────────────────────────────────────────────────────────
# Hybrid Pipeline — PaddleOCR Chunks
# ─────────────────────────────────────────────────────────────────────────────

class OcrChunk(Base):
    """
    Stores OCR-recognized text blocks from PaddleOCR.
    Each row is one detected text region on a page, with its bounding box,
    confidence score, detected language, and reading order position.
    """
    __tablename__ = "ocr_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False, default=1.0)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # ISO 639-1 code
    # Normalized bounding box (0.0 – 1.0 relative to page dimensions)
    bbox_x0: Mapped[Optional[float]] = mapped_column(nullable=True)
    bbox_y0: Mapped[Optional[float]] = mapped_column(nullable=True)
    bbox_x1: Mapped[Optional[float]] = mapped_column(nullable=True)
    bbox_y1: Mapped[Optional[float]] = mapped_column(nullable=True)
    reading_order: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="ocr_chunks")


# ─────────────────────────────────────────────────────────────────────────────
# Hybrid Pipeline — BGE-M3 Text Embedding Chunks
# ─────────────────────────────────────────────────────────────────────────────

class TextEmbeddingChunk(Base):
    """
    Tracks every text chunk encoded by BGE-M3 and upserted to the
    Qdrant 'text_chunks' collection. Maintains a pointer (qdrant_point_id)
    for deletion and re-indexing operations.
    """
    __tablename__ = "text_embedding_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    folder_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(nullable=True)
    chunk_index: Mapped[int] = mapped_column(nullable=False, default=0)  # within-page ordering
    chunk_type: Mapped[str] = mapped_column(String(50), nullable=False)  # paragraph/heading/table/ocr/section
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Metadata for semantic chunking
    section: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    heading: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hierarchy: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_section: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    qdrant_point_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="text_embedding_chunks")


# ─────────────────────────────────────────────────────────────────────────────
# Hybrid Pipeline — AI-Generated Document Summaries
# ─────────────────────────────────────────────────────────────────────────────

class DocumentSummary(Base):
    """
    Stores the Gemini Flash-generated summary and document-level metadata
    such as reading time estimate and a complexity score (0.0 – 1.0).
    One row per document (UNIQUE constraint on document_id).
    """
    __tablename__ = "document_summaries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reading_time_minutes: Mapped[Optional[int]] = mapped_column(nullable=True)
    complexity_score: Mapped[Optional[float]] = mapped_column(nullable=True)  # 0.0 (simple) – 1.0 (complex)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    document_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # contract/report/research/invoice/etc.
    topics_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of topic strings
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="summary")


# ─────────────────────────────────────────────────────────────────────────────
# Hybrid Pipeline — Document Keywords
# ─────────────────────────────────────────────────────────────────────────────

class DocumentKeyword(Base):
    """
    Stores extracted keywords with relevance scores (TF-IDF / LLM-ranked).
    Multiple rows per document, one per keyword.
    """
    __tablename__ = "document_keywords"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[Optional[float]] = mapped_column(nullable=True)  # 0.0 – 1.0 relevance
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="keywords")


# ─────────────────────────────────────────────────────────────────────────────
# Hybrid Pipeline — Named Entities
# ─────────────────────────────────────────────────────────────────────────────

class DocumentEntity(Base):
    """
    Stores named entities extracted from the document.
    Entity types: PERSON, ORG, DATE, MONEY, LOCATION, PRODUCT, LAW, etc.
    """
    __tablename__ = "document_entities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    entity_text: Mapped[str] = mapped_column(String(500), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)  # PERSON/ORG/DATE/MONEY/LOCATION/PRODUCT/LAW
    page_number: Mapped[Optional[int]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="entities")


# ─────────────────────────────────────────────────────────────────────────────
# Hybrid Pipeline — Processing Job Registry
# ─────────────────────────────────────────────────────────────────────────────

class ProcessingJob(Base):
    """
    Tracks the status of each background Celery task in the hybrid pipeline.
    Used by the Processing Dashboard to show per-document, per-stage progress.
    Stores timing metrics for observability.
    """
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)  # docling_parse/ocr/bge_embed/metadata_enrichment
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")  # queued/running/completed/failed
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON blob: {"duration_ms": 1234, "pages_processed": 5, "chunks_created": 42}
    metrics_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    document: Mapped["Document"] = relationship(back_populates="processing_jobs")

# ─────────────────────────────────────────────────────────────────────────────
# Sprint 4 — Processing Profiling Metrics
# ─────────────────────────────────────────────────────────────────────────────

class ProcessingMetrics(Base):
    """
    Tracks detailed performance metrics for each stage of document ingestion.
    Metrics include CPU usage, GPU memory, and duration for Upload, OCR,
    Embedding, Metadata, Vision, and Database operations.
    """
    __tablename__ = "processing_metrics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)  # upload/ocr/embedding/metadata/vision/database/qdrant
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    cpu_percent: Mapped[Optional[float]] = mapped_column(nullable=True)
    gpu_memory_mb: Mapped[Optional[float]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="in_progress")  # in_progress/completed/failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    document: Mapped["Document"] = relationship(back_populates="processing_metrics")


# ─────────────────────────────────────────────────────────────────────────────
# Sprint 5 — Knowledge Graph & Discovery
# ─────────────────────────────────────────────────────────────────────────────

class KnowledgeGraphEdge(Base):
    """
    Connects documents automatically based on vector similarity, shared entities, or explicit references.
    """
    __tablename__ = "knowledge_graph_edges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    org_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    source_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    target_document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False) # e.g., 'similarity', 'reference', 'shared_entity'
    weight: Mapped[float] = mapped_column(nullable=False, default=1.0) # Confidence or similarity score
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # E.g., shared entity names
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    source_document: Mapped["Document"] = relationship(foreign_keys=[source_document_id])
    target_document: Mapped["Document"] = relationship(foreign_keys=[target_document_id])

from sqlalchemy.dialects.postgresql import JSONB

class FailedJob(Base):
    __tablename__ = "failed_jobs"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    args: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    kwargs: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    stack_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="failed", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class UserDocumentInteraction(Base):
    """
    Tracks user interaction with documents to fuel 'Recently Viewed' and 'Frequently Used' features.
    """
    __tablename__ = "user_document_interactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, server_default=func.uuid_generate_v4())
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    interaction_type: Mapped[str] = mapped_column(String(50), nullable=False) # 'viewed', 'searched', 'cited'
    count: Mapped[int] = mapped_column(nullable=False, default=1)
    last_interaction_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    user: Mapped["User"] = relationship()
    document: Mapped["Document"] = relationship()



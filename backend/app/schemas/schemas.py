from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
import uuid

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    org_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool

    class Config:
        from_attributes = True

# Organization Schemas
class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    domain: Optional[str] = None

    class Config:
        from_attributes = True

# Token Schemas
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    organization: OrganizationResponse
    role: str


# ---------------------------------------------------------------------------
# Day 8: Search Schemas
# ---------------------------------------------------------------------------

from enum import Enum

class SearchMode(str, Enum):
    HYBRID = "hybrid"
    VISION = "vision"
    TEXT = "text"
    KEYWORD = "keyword"

class MetadataFilters(BaseModel):
    title: Optional[str] = Field(None, description="Filter by document title")
    department: Optional[str] = Field(None, description="Filter by department")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    author: Optional[str] = Field(None, description="Filter by author")
    document_type: Optional[str] = Field(None, description="Filter by document type")

class SearchRequest(BaseModel):
    """Input payload for POST /api/v1/search."""
    query: str = Field(..., min_length=1, max_length=1000, description="Natural-language search query")
    search_mode: SearchMode = Field(default=SearchMode.HYBRID, description="Search mode to use")
    folder_id: Optional[uuid.UUID] = Field(None, description="Optional folder UUID to narrow search scope")
    document_id: Optional[uuid.UUID] = Field(None, description="Optional document UUID to narrow search scope")
    metadata_filters: Optional[MetadataFilters] = Field(None, description="Optional metadata filters to pre-filter documents")
    top_k: int = Field(default=10, ge=1, le=100, description="Maximum number of results to return")



class SearchResult(BaseModel):
    """A single matched page returned by the search endpoint."""
    page_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    page_number: int
    score: float = Field(..., description="RRF fused relevance score (higher = more relevant)")
    text_snippet: str = Field("", description="First 200 characters of extracted page text")
    s3_signed_url: str = Field("", description="Time-limited presigned URL to the rendered page PNG")
    org_id: uuid.UUID

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    """Full response envelope for the search endpoint."""
    results: List[SearchResult]
    total: int = Field(..., description="Total number of results returned")
    query_time_ms: int = Field(..., description="End-to-end search latency in milliseconds")


# ---------------------------------------------------------------------------
# Day 10: Telemetry Schemas
# ---------------------------------------------------------------------------

class SearchLogResponse(BaseModel):
    """Schema for a recorded search telemetry event."""
    id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    org_id: uuid.UUID
    query: str
    result_count: int
    latency_ms: int

    class Config:
        from_attributes = True


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    organization_name: str
    role: str

# ---------------------------------------------------------------------------
# Sprint 5: Hybrid Pipeline Schemas
# ---------------------------------------------------------------------------

class KeywordResponse(BaseModel):
    keyword: str
    score: float

    class Config:
        from_attributes = True

class EntityResponse(BaseModel):
    entity_text: str
    entity_type: str

    class Config:
        from_attributes = True

class DocumentMetadataResponse(BaseModel):
    summary: Optional[str] = None
    executive_summary: Optional[str] = None
    reading_time_minutes: Optional[int] = None
    complexity_score: Optional[float] = None
    importance_score: Optional[float] = None
    risk_score: Optional[float] = None
    risk_issues: List[str] = Field(default_factory=list)
    document_type: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    keywords: List[KeywordResponse] = Field(default_factory=list)
    entities: List[EntityResponse] = Field(default_factory=list)
    category: Optional[str] = None
    department: Optional[str] = None

class OcrChunkResponse(BaseModel):
    id: uuid.UUID
    page_number: int
    text: str
    confidence: float
    bbox_x0: Optional[float] = None
    bbox_y0: Optional[float] = None
    bbox_x1: Optional[float] = None
    bbox_y1: Optional[float] = None

    class Config:
        from_attributes = True

# =============================================================================
# Sprint 13 — Enterprise Workflow Schemas
# =============================================================================

class DocumentVersionResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    file_size: int
    change_note: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True

class DocumentCommentBase(BaseModel):
    content: str
    parent_id: Optional[uuid.UUID] = None

class DocumentCommentCreate(DocumentCommentBase):
    pass

class DocumentCommentResponse(DocumentCommentBase):
    id: uuid.UUID
    document_id: uuid.UUID
    user_id: uuid.UUID
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

class DocumentTaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    assigned_to: uuid.UUID
    due_date: Optional[str] = None

class DocumentTaskCreate(DocumentTaskBase):
    pass

class DocumentTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[str] = None

class DocumentTaskResponse(DocumentTaskBase):
    id: uuid.UUID
    document_id: uuid.UUID
    assigned_by: uuid.UUID
    status: str
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    org_id: uuid.UUID
    message: str
    notification_type: str
    link: Optional[str] = None
    is_read: bool
    created_at: str

    class Config:
        from_attributes = True

class NotificationUpdate(BaseModel):
    is_read: bool

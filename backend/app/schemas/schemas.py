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
    org_name: str = Field(..., min_length=1)

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

class SearchRequest(BaseModel):
    """Input payload for POST /api/v1/search."""
    query: str = Field(..., min_length=1, max_length=1000, description="Natural-language search query")
    folder_id: Optional[uuid.UUID] = Field(None, description="Optional folder UUID to narrow search scope")
    document_id: Optional[uuid.UUID] = Field(None, description="Optional document UUID to narrow search scope")
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



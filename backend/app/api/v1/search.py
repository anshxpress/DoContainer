"""
Sprint 3 — Day 8: FastAPI Search Route  /api/v1/search
          Day 6: Permission enforcement via get_current_user_context
          Day 10: Search telemetry logging to PostgreSQL search_logs table

Accepts a POST body with a natural-language query, optional folder filter,
and page-size. Returns RRF-fused semantic + keyword results with presigned
S3 image URLs for visual citations.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user_context, CurrentUserContext, PermissionChecker
from backend.app.core.db import get_db
from backend.app.models.models import TeamMembership
from backend.app.repositories.base_repo import search_log_repo
from backend.app.schemas.schemas import SearchRequest, SearchResponse, SearchResult as SearchResultSchema
from backend.app.services.search_service import hybrid_search, SearchResult as SvcSearchResult
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper: derive team_ids for the current user
# ---------------------------------------------------------------------------

def _get_user_team_ids(db: Session, user_id: uuid.UUID, org_id: str) -> List[str]:
    """
    Return a list of team UUID strings the given user belongs to within org_id.
    Used to build the permission filter for both Qdrant and FTS queries.
    """
    memberships = (
        db.query(TeamMembership)
        .filter(TeamMembership.user_id == user_id)
        .all()
    )
    return [str(tm.team_id) for tm in memberships]


# ---------------------------------------------------------------------------
# Helper: convert service SearchResult → Pydantic schema
# ---------------------------------------------------------------------------

def _to_schema(result: SvcSearchResult) -> SearchResultSchema:
    return SearchResultSchema(
        page_id=uuid.UUID(result.page_id),
        document_id=uuid.UUID(result.document_id),
        document_name=result.document_name,
        page_number=result.page_number,
        score=result.score,
        text_snippet=result.text_snippet,
        s3_signed_url=result.s3_signed_url,
        org_id=uuid.UUID(result.org_id),
    )


# ---------------------------------------------------------------------------
# POST /search
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=SearchResponse,
    summary="Semantic + keyword hybrid search",
    description=(
        "Performs a hybrid search combining Qdrant multi-vector semantic search "
        "and PostgreSQL full-text search, fused via Reciprocal Rank Fusion. "
        "Results are filtered to pages accessible to the authenticated user. "
        "Each result includes a time-limited presigned S3 URL for the rendered page image."
    ),
)
def search_documents(
    request: SearchRequest,
    # Day 6: PermissionChecker enforces that the user has the 'search:documents' permission.
    # Organisation Admin and higher roles inherit this automatically via the PermissionChecker
    # Super Admin bypass. Adjust the permission name to match your roles/permissions seeding.
    current_context: CurrentUserContext = Depends(PermissionChecker("search:documents")),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """
    POST /api/v1/search

    Required permission: `search:documents`

    Request body:
        query     — Natural-language search string (1–1000 chars)
        folder_id — Optional UUID to scope search to one folder
        top_k     — Max results (1–100, default 10)

    Returns:
        SearchResponse with results, total count, and query latency.
    """
    t_start = time.monotonic()

    # Resolve the user's team memberships for permission filtering
    team_ids = _get_user_team_ids(db, current_context.user.id, current_context.org_id)

    # Run hybrid search
    svc_results = hybrid_search(
        db=db,
        query=request.query,
        org_id=current_context.org_id,
        team_ids=team_ids,
        folder_id=str(request.folder_id) if request.folder_id else None,
        document_id=str(request.document_id) if request.document_id else None,
        metadata_filters=request.metadata_filters,
        search_mode=request.search_mode,
        top_k=request.top_k,
    )

    latency_ms = int((time.monotonic() - t_start) * 1000)

    # Convert service objects → Pydantic schema objects
    schema_results = [_to_schema(r) for r in svc_results]

    # -------------------------------------------------------------------------
    # Day 10: Persist telemetry asynchronously (best-effort — never fail search)
    # -------------------------------------------------------------------------
    try:
        search_log_repo.create(
            db,
            obj_in={
                "user_id": current_context.user.id,
                "org_id": current_context.org_id,
                "query": request.query,
                "result_count": len(schema_results),
                "latency_ms": latency_ms,
            },
        )
    except Exception as log_exc:
        logger.warning("Failed to persist search telemetry: %s", log_exc)

    return SearchResponse(
        results=schema_results,
        total=len(schema_results),
        query_time_ms=latency_ms,
    )

class SearchSuggestionsResponse(BaseModel):
    suggestions: List[str]

@router.get(
    "/suggestions",
    response_model=SearchSuggestionsResponse,
    summary="Get search suggestions for a query"
)
def get_search_suggestions(
    query: str,
    current_context: CurrentUserContext = Depends(PermissionChecker("search:documents")),
):
    """
    GET /api/v1/search/suggestions
    Uses the LLM query expansion to return search suggestions based on the user's input.
    """
    from backend.app.services.llm_client import get_llm_client
    
    if not query or len(query) < 3:
        return SearchSuggestionsResponse(suggestions=[])
        
    try:
        llm = get_llm_client()
        expansion = llm.expand_query_sync(query)
        suggestions = expansion.get("suggestions", [])
        return SearchSuggestionsResponse(suggestions=suggestions)
    except Exception as exc:
        logger.warning("Failed to generate search suggestions: %s", exc)
        return SearchSuggestionsResponse(suggestions=[])

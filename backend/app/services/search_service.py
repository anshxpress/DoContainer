"""
Sprint 3 — Day 5 & 7: Hybrid Search Service with Reciprocal Rank Fusion (RRF)
and Visual Citation Metadata.

Orchestrates the two retrieval backends:
  1. Qdrant multi-vector semantic search (vision embeddings)
  2. PostgreSQL full-text search (keyword fallback)

Fuses their results using RRF, generates S3 presigned URLs for each matched
page image, and returns structured SearchResult objects.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from backend.app.core.qdrant import search_pages
from backend.app.core.s3 import s3_storage
from backend.app.repositories.base_repo import document_page_repo
from backend.app.services.retriever import get_retriever
from opentelemetry import trace
from backend.app.core.telemetry import tracer


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """
    Day 7: Visual citation payload returned per matched page.

    Fields:
        page_id:         UUID of the DocumentPage row.
        document_id:     UUID of the parent Document.
        document_name:   Human-readable document name.
        page_number:     1-based page number within the document.
        score:           RRF fused relevance score (higher = more relevant).
        text_snippet:    First 200 characters of extracted text_content.
        s3_signed_url:   Time-limited presigned URL to the rendered PNG image.
        org_id:          Organisation UUID (for audit purposes).
    """
    page_id: str
    document_id: str
    document_name: str
    page_number: int
    score: float
    text_snippet: str
    s3_signed_url: str
    org_id: str


# ---------------------------------------------------------------------------
# RRF implementation
# ---------------------------------------------------------------------------

def _reciprocal_rank_fusion(
    ranked_lists: List[List[str]],
    k: int = 60,
) -> Dict[str, float]:
    """
    Day 5: Reciprocal Rank Fusion.

    Given multiple ranked lists of document IDs (page IDs in our case),
    computes a fused score for each unique ID.

    Formula: score(d) = Σ  1 / (k + rank(d))
                       over all lists where d appears.

    Args:
        ranked_lists: Each inner list is a ranked sequence of page ID strings,
                      best-first (index 0 = rank 1).
        k:            Constant that controls the impact of high rankings.
                      RRF paper recommends k=60.

    Returns:
        Dict mapping page_id → fused score (higher = better).
    """
    scores: Dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, page_id in enumerate(ranked, start=1):
            scores[page_id] = scores.get(page_id, 0.0) + 1.0 / (k + rank)
    return scores


# ---------------------------------------------------------------------------
# Presigned URL helper
# ---------------------------------------------------------------------------

def _get_presigned_url(png_storage_path: str, expiry: int = 3600) -> str:
    """
    Generate an S3/MinIO presigned URL for a rendered page PNG.
    Returns an empty string when MinIO is unreachable (dev fallback).
    """
    try:
        return s3_storage.generate_presigned_url(png_storage_path, expiration=expiry) or ""
    except Exception as exc:
        logger.warning(
            "Failed to generate presigned URL for '%s': %s", png_storage_path, exc
        )
        return ""


# ---------------------------------------------------------------------------
# Main hybrid search function
# ---------------------------------------------------------------------------

@tracer.start_as_current_span("hybrid_search")
def hybrid_search(
    db: Session,
    query: str,
    org_id: str,
    team_ids: List[str],
    folder_id: Optional[str] = None,
    document_id: Optional[str] = None,
    top_k: int = 10,
    k_rrf: int = 60,
    url_expiry_seconds: int = 3600,
) -> List[SearchResult]:
    """
    Day 5 + Day 7: Hybrid Search with RRF and Visual Citations.
    """
    span = trace.get_current_span()
    span.set_attribute("org_id", org_id)
    span.set_attribute("query", query)

    if not query or not query.strip():
        return []

    retriever = get_retriever()

    # -------------------------------------------------------------------------
    # Step 1: Generate multi-vector query embedding
    # -------------------------------------------------------------------------
    try:
        query_vectors = retriever.embed_query(query)
    except Exception as exc:
        logger.error("Retriever.embed_query failed: %s", exc)
        query_vectors = []

    # -------------------------------------------------------------------------
    # Step 2: Qdrant multi-vector semantic search
    # -------------------------------------------------------------------------
    qdrant_ranked: List[str] = []  # page_id strings, best-first
    if query_vectors:
        try:
            scored_points = search_pages(
                query_vectors=query_vectors,
                org_id=org_id,
                team_ids=team_ids,
                folder_id=folder_id,
                document_id=document_id,
                limit=top_k * 2,  # fetch extra so RRF has more to blend
            )
            qdrant_ranked = [str(sp.id) for sp in scored_points]
            logger.debug("Qdrant returned %d results for query '%s'", len(qdrant_ranked), query)
        except Exception as exc:
            logger.warning("Qdrant search failed: %s — skipping vision results.", exc)

    # -------------------------------------------------------------------------
    # Step 3: PostgreSQL full-text keyword search
    # -------------------------------------------------------------------------
    fts_ranked: List[str] = []
    try:
        fts_pages = document_page_repo.search_pages_fts(
            db,
            org_id=org_id,
            team_ids=team_ids,
            query_text=query,
            folder_id=folder_id,
            document_id=document_id,
            limit=top_k * 2,
        )
        fts_ranked = [str(p.id) for p in fts_pages]
        logger.debug("FTS returned %d results for query '%s'", len(fts_ranked), query)
    except Exception as exc:
        logger.warning("FTS search failed: %s — skipping keyword results.", exc)

    # -------------------------------------------------------------------------
    # Step 4: Reciprocal Rank Fusion
    # -------------------------------------------------------------------------
    fused_scores = _reciprocal_rank_fusion(
        ranked_lists=[qdrant_ranked, fts_ranked],
        k=k_rrf,
    )

    if not fused_scores:
        logger.info("No results found for query '%s'", query)
        return []

    # Sort by fused score descending, take top_k
    top_ids_scores = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    # -------------------------------------------------------------------------
    # Step 5-7: Fetch page details and generate presigned URLs
    # -------------------------------------------------------------------------
    results: List[SearchResult] = []
    for page_id_str, score in top_ids_scores:
        try:
            page_uuid = uuid.UUID(page_id_str)
        except ValueError:
            logger.warning("Invalid page UUID in fused results: %s", page_id_str)
            continue

        page = document_page_repo.get(db, id=page_uuid)
        if not page:
            logger.debug("Page %s not found in DB (may have been deleted)", page_id_str)
            continue

        doc = page.document
        if not doc:
            continue

        # Generate presigned URL (Day 7)
        signed_url = _get_presigned_url(page.png_storage_path, expiry=url_expiry_seconds)

        # Text snippet (first 200 chars)
        snippet = (page.text_content or "")[:200]

        results.append(
            SearchResult(
                page_id=page_id_str,
                document_id=str(doc.id),
                document_name=doc.name,
                page_number=page.page_number,
                score=round(score, 6),
                text_snippet=snippet,
                s3_signed_url=signed_url,
                org_id=str(doc.org_id),
            )
        )

    logger.info(
        "hybrid_search: returned %d results for query='%s', org_id='%s'",
        len(results), query, org_id,
    )
    return results

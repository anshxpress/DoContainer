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

from backend.app.core.qdrant import search_pages, search_text_chunks
from backend.app.core.s3 import s3_storage
from backend.app.repositories.base_repo import document_page_repo
from backend.app.services.retriever import get_retriever
from backend.app.services.bge_service import get_bge_service, get_reranker_service
from backend.app.schemas.schemas import SearchMode
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
    search_mode: SearchMode = SearchMode.HYBRID,
    top_k: int = 10,
    k_rrf: int = 60,
    url_expiry_seconds: int = 3600,
) -> List[SearchResult]:
    """
    Day 5 + Day 7 + Sprint 5: Hybrid Search with 3-way RRF, BGE Reranking, and Visual Citations.
    """
    span = trace.get_current_span()
    span.set_attribute("org_id", org_id)
    span.set_attribute("query", query)
    span.set_attribute("search_mode", search_mode.value)

    if not query or not query.strip():
        return []

    retriever = get_retriever()
    bge_service = get_bge_service()
    reranker_service = get_reranker_service()

    qdrant_ranked: List[str] = []
    text_ranked: List[str] = []
    fts_ranked: List[str] = []

    # -------------------------------------------------------------------------
    # 1. Vision Search (ColQwen2)
    # -------------------------------------------------------------------------
    if search_mode in (SearchMode.HYBRID, SearchMode.VISION):
        try:
            query_vectors = retriever.embed_query(query)
            if query_vectors:
                scored_points = search_pages(
                    query_vectors=query_vectors,
                    org_id=org_id,
                    team_ids=team_ids,
                    folder_id=folder_id,
                    document_id=document_id,
                    limit=top_k * 2,
                )
                qdrant_ranked = [str(sp.id) for sp in scored_points]
        except Exception as exc:
            logger.warning("Qdrant vision search failed: %s", exc)

    # -------------------------------------------------------------------------
    # 2. Text Search (BGE-M3)
    # -------------------------------------------------------------------------
    if search_mode in (SearchMode.HYBRID, SearchMode.TEXT):
        try:
            dense_query = bge_service.encode_query(query)
            if dense_query and any(v != 0.0 for v in dense_query):
                scored_chunks = search_text_chunks(
                    query_vector=dense_query,
                    org_id=org_id,
                    team_ids=team_ids,
                    folder_id=folder_id,
                    document_id=document_id,
                    limit=top_k * 4,
                )
                
                # Fast batched lookup: DocumentPage by (document_id, page_number)
                doc_ids = list({uuid.UUID(sp.payload["document_id"]) for sp in scored_chunks if "document_id" in sp.payload})
                if doc_ids:
                    from backend.app.models.models import DocumentPage
                    pages = db.query(DocumentPage).filter(
                        DocumentPage.document_id.in_(doc_ids)
                    ).all()
                    
                    page_map = {(p.document_id, p.page_number): str(p.id) for p in pages}
                    
                    for sp in scored_chunks:
                        try:
                            d_uuid = uuid.UUID(sp.payload["document_id"])
                            p_num = sp.payload.get("page_number", 1)
                            page_id_str = page_map.get((d_uuid, p_num))
                            if page_id_str and page_id_str not in text_ranked:
                                text_ranked.append(page_id_str)
                        except Exception:
                            continue
        except Exception as exc:
            logger.warning("Qdrant text chunk search failed: %s", exc)

    # -------------------------------------------------------------------------
    # 3. Keyword Search (FTS)
    # -------------------------------------------------------------------------
    if search_mode in (SearchMode.HYBRID, SearchMode.KEYWORD):
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
        except Exception as exc:
            logger.warning("FTS search failed: %s", exc)

    # -------------------------------------------------------------------------
    # 4. Reciprocal Rank Fusion (3-way)
    # -------------------------------------------------------------------------
    fused_scores = _reciprocal_rank_fusion(
        ranked_lists=[qdrant_ranked, text_ranked, fts_ranked],
        k=k_rrf,
    )

    if not fused_scores:
        logger.info("No results found for query '%s'", query)
        return []

    # Fetch top ~20 candidates for reranking
    candidates = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:max(top_k, 20)]
    
    pages_dict = {}
    for pid, _ in candidates:
        try:
            page = document_page_repo.get(db, id=uuid.UUID(pid))
            if page and page.document:
                pages_dict[pid] = page
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # 5. Cross-Encoder Reranking
    # -------------------------------------------------------------------------
    if search_mode in (SearchMode.HYBRID, SearchMode.TEXT) and pages_dict:
        try:
            passages = [pages_dict[pid].text_content or "" for pid, _ in candidates if pid in pages_dict]
            reranked_scores = reranker_service.rerank(query, passages)
            
            reranked_results = []
            valid_idx = 0
            for pid, original_score in candidates:
                if pid in pages_dict:
                    score = reranked_scores[valid_idx]
                    reranked_results.append((pid, score))
                    valid_idx += 1
            
            top_ids_scores = sorted(reranked_results, key=lambda x: x[1], reverse=True)[:top_k]
        except Exception as exc:
            logger.warning("Reranking failed, falling back to RRF: %s", exc)
            top_ids_scores = candidates[:top_k]
    else:
        top_ids_scores = candidates[:top_k]

    # -------------------------------------------------------------------------
    # 6. Build Results
    # -------------------------------------------------------------------------
    results: List[SearchResult] = []
    for page_id_str, score in top_ids_scores:
        if page_id_str not in pages_dict:
            continue
        page = pages_dict[page_id_str]
        doc = page.document
        
        signed_url = _get_presigned_url(page.png_storage_path, expiry=url_expiry_seconds)
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

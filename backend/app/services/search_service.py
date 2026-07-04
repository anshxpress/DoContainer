"""
Sprint 3 — Low Latency Hybrid Search Service
"""
from __future__ import annotations

import logging
import uuid
import json
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.app.core.qdrant import search_pages, search_text_chunks
from backend.app.core.s3 import s3_storage
from backend.app.repositories.base_repo import document_page_repo
from backend.app.services.retriever import get_retriever
from backend.app.services.bge_service import get_bge_service, get_reranker_service
from backend.app.schemas.schemas import SearchMode, MetadataFilters
from opentelemetry import trace
from backend.app.core.telemetry import tracer
from backend.app.core.cache import get_cache, set_cache, generate_cache_key
from backend.app.models.models import Document, DocumentSummary, DocumentPage
from backend.app.services.llm_client import get_llm_client
from backend.app.core.config import features

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    page_id: str
    document_id: str
    document_name: str
    page_number: int
    score: float
    text_snippet: str
    s3_signed_url: str
    org_id: str

def _reciprocal_rank_fusion(ranked_lists: List[List[str]], k: int = 60) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, page_id in enumerate(ranked, start=1):
            scores[page_id] = scores.get(page_id, 0.0) + 1.0 / (k + rank)
    return scores

def _get_presigned_url(png_storage_path: str, expiry: int = 3600) -> str:
    try:
        return s3_storage.generate_presigned_url(png_storage_path, expiration=expiry) or ""
    except Exception as exc:
        logger.warning("Failed to generate presigned URL for '%s': %s", png_storage_path, exc)
        return ""

@tracer.start_as_current_span("hybrid_search")
def hybrid_search(
    db: Session,
    query: str,
    org_id: str,
    team_ids: List[str],
    folder_id: Optional[str] = None,
    document_id: Optional[str] = None,
    metadata_filters: Optional[MetadataFilters] = None,
    search_mode: SearchMode = SearchMode.HYBRID,
    top_k: int = 10,
    k_rrf: int = 60,
    url_expiry_seconds: int = 3600,
) -> List[SearchResult]:
    span = trace.get_current_span()
    span.set_attribute("org_id", org_id)
    span.set_attribute("query", query)
    span.set_attribute("search_mode", search_mode.value)

    if not query or not query.strip():
        return []

    # 1. Query Cache Check
    cache_kwargs = {
        "query": query,
        "org_id": org_id,
        "team_ids": team_ids,
        "folder_id": folder_id,
        "document_id": document_id,
        "search_mode": search_mode.value,
        "top_k": top_k,
    }
    if metadata_filters:
        cache_kwargs["metadata_filters"] = metadata_filters.model_dump()
        
    cache_key = generate_cache_key("search", **cache_kwargs)
    cached_result = get_cache(cache_key)
    if cached_result:
        logger.info("Cache HIT for query '%s'", query)
        return [SearchResult(**r) for r in cached_result]

    retriever = get_retriever()
    bge_service = get_bge_service()
    reranker_service = get_reranker_service()
    llm_client = get_llm_client()

    # 1.5 Query Expansion
    expanded_search_term = query
    try:
        expansion = llm_client.expand_query_sync(query)
        expanded_search_term = expansion.get("expanded_query", query)
        
        # Optionally merge inferred filters
        inferred_filters = expansion.get("filters", {})
        if inferred_filters and not metadata_filters:
            metadata_filters = MetadataFilters()
        if inferred_filters.get("document_type"):
            metadata_filters.document_type = inferred_filters.get("document_type")
            
        logger.info("Query expansion: '%s' -> '%s'", query, expanded_search_term)
    except Exception as exc:
        logger.warning("Query expansion failed: %s", exc)

    # 2. Metadata Pre-filtering (PostgreSQL)
    target_document_ids = None
    if document_id:
        target_document_ids = [document_id]

    if metadata_filters:
        q = db.query(Document.id).outerjoin(DocumentSummary, Document.id == DocumentSummary.document_id)
        q = q.filter(Document.org_id == uuid.UUID(org_id))
        if folder_id:
            q = q.filter(Document.folder_id == uuid.UUID(folder_id))
            
        if metadata_filters.title:
            q = q.filter(Document.name.ilike(f"%{metadata_filters.title}%"))
        if metadata_filters.department and features.ENABLE_ORGANIZATION:
            q = q.filter(Document.department.ilike(f"%{metadata_filters.department}%"))
        if metadata_filters.document_type:
            q = q.filter(DocumentSummary.document_type.ilike(f"%{metadata_filters.document_type}%"))
        if metadata_filters.tags:
            for tag in metadata_filters.tags:
                q = q.filter(DocumentSummary.topics_json.ilike(f"%{tag}%"))
                
        # Execute query to get matching document_ids
        matched_docs = q.all()
        matched_ids = [str(d[0]) for d in matched_docs]
        
        # Intersect with explicit document_id if provided
        if target_document_ids is not None:
            target_document_ids = list(set(target_document_ids).intersection(set(matched_ids)))
        else:
            target_document_ids = matched_ids
            
        # If metadata filters yielded no results, return early
        if not target_document_ids:
            logger.info("Metadata filters yielded 0 documents. Returning empty.")
            return []

    qdrant_ranked: List[str] = []
    text_ranked: List[str] = []
    fts_ranked: List[str] = []
    
    max_semantic_score = 0.0

    # 3. Vision Search (ColQwen2)
    if search_mode in (SearchMode.HYBRID, SearchMode.VISION):
        try:
            query_vectors = retriever.embed_query(expanded_search_term)
            if query_vectors:
                scored_points = search_pages(
                    query_vectors=query_vectors,
                    org_id=org_id,
                    team_ids=team_ids,
                    folder_id=folder_id,
                    document_ids=target_document_ids,
                    limit=top_k * 2,
                )
                qdrant_ranked = [str(sp.id) for sp in scored_points]
                for sp in scored_points:
                    if sp.score > max_semantic_score:
                        max_semantic_score = sp.score
        except Exception as exc:
            logger.warning("Qdrant vision search failed: %s", exc)

    # 4. Text Search (BGE-M3)
    if search_mode in (SearchMode.HYBRID, SearchMode.TEXT):
        try:
            dense_query = bge_service.encode_query(expanded_search_term)
            if dense_query and any(v != 0.0 for v in dense_query):
                scored_chunks = search_text_chunks(
                    query_vector=dense_query,
                    org_id=org_id,
                    team_ids=team_ids,
                    folder_id=folder_id,
                    document_ids=target_document_ids,
                    limit=top_k * 4,
                )
                
                # Update max semantic score
                for sp in scored_chunks:
                    if sp.score > max_semantic_score:
                        max_semantic_score = sp.score
                
                doc_ids = list({uuid.UUID(sp.payload["document_id"]) for sp in scored_chunks if "document_id" in sp.payload})
                if doc_ids:
                    pages = db.query(DocumentPage).filter(DocumentPage.document_id.in_(doc_ids)).all()
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

    # 5. Keyword Search (FTS)
    if search_mode in (SearchMode.HYBRID, SearchMode.KEYWORD):
        try:
            fts_pages = document_page_repo.search_pages_fts(
                db,
                org_id=org_id,
                team_ids=team_ids,
                query_text=expanded_search_term,
                folder_id=folder_id,
                # Note: FTS currently only accepts single document_id in repo.
                # Since we already have target_document_ids, we can implement it directly or just use it.
                # If target_document_ids has a few, maybe we skip FTS or pass them.
                # For now we just pass document_id if it was passed, FTS doesn't natively take a list in the current repo,
                # but let's pass it anyway if it's a single ID, otherwise FTS searches all and we filter post-FTS.
                document_id=document_id, 
                limit=top_k * 4,
            )
            for p in fts_pages:
                if target_document_ids is None or str(p.document_id) in target_document_ids:
                    if str(p.id) not in fts_ranked:
                        fts_ranked.append(str(p.id))
        except Exception as exc:
            logger.warning("FTS search failed: %s", exc)

    # 6. Reciprocal Rank Fusion (3-way)
    fused_scores = _reciprocal_rank_fusion(
        ranked_lists=[qdrant_ranked, text_ranked, fts_ranked],
        k=k_rrf,
    )

    if not fused_scores:
        logger.info("No results found for query '%s'", query)
        return []

    # Fetch top candidates
    candidates = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:max(top_k, 20)]
    
    pages_dict = {}
    for pid, _ in candidates:
        try:
            page = document_page_repo.get(db, id=uuid.UUID(pid))
            if page and page.document:
                pages_dict[pid] = page
        except Exception:
            pass

    # 7. Dynamic Cross-Encoder Reranking
    RERANKER_THRESHOLD = 0.80
    if search_mode in (SearchMode.HYBRID, SearchMode.TEXT) and pages_dict:
        if max_semantic_score >= RERANKER_THRESHOLD:
            logger.info("Skipping reranker (confidence %.2f >= %.2f)", max_semantic_score, RERANKER_THRESHOLD)
            top_ids_scores = candidates[:top_k]
        else:
            try:
                passages = [pages_dict[pid].text_content or "" for pid, _ in candidates if pid in pages_dict]
                reranked_scores = reranker_service.rerank(expanded_search_term, passages)
                
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

    # 8. Build Results
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

    # 9. Set Cache
    logger.info("hybrid_search: returned %d results for query='%s', org_id='%s'", len(results), query, org_id)
    set_cache(cache_key, [r.__dict__ for r in results], expire=300)

    return results

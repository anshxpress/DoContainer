"""
Hybrid Pipeline — OCR, Docling, BGE-M3, and Metadata Celery Tasks

Four new tasks that run on the 'ocr-pipeline' Celery queue after the existing
embed_and_index_task completes the ColQwen2 vision embedding:

  1. docling_parse_task   — Docling structure-aware parsing
  2. ocr_task            — PaddleOCR on scanned pages
  3. bge_embed_task      — BGE-M3 text embedding → Qdrant 'text_chunks'
  4. metadata_enrichment_task — Gemini Flash metadata generation
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import concurrent.futures
import tempfile
import uuid
import time
import botocore.exceptions
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.app.tasks.celery_app import celery_app
from backend.app.core.config import settings
from backend.app.core.db import SessionLocal
from backend.app.core.s3 import s3_storage
from backend.app.core.qdrant import qdrant_client
from backend.app.core.profiler import StageProfiler
import concurrent.futures
from backend.app.models.models import (
    DocumentParseElement,
    OcrChunk,
    TextEmbeddingChunk,
    ProcessingJob,
)
from backend.app.repositories.base_repo import document_repo, document_page_repo
from qdrant_client.models import PointStruct
from opentelemetry import trace
from backend.app.core.telemetry import tracer

logger = logging.getLogger(__name__)

# Re-use the DLQ handler from the main task module
from backend.app.tasks.tasks import handle_task_failure


# ---------------------------------------------------------------------------
# Helper: ProcessingJob lifecycle
# ---------------------------------------------------------------------------

def _create_job(db, document_id: uuid.UUID, org_id: uuid.UUID, job_type: str, celery_task_id: str) -> ProcessingJob:
    job = ProcessingJob(
        document_id=document_id,
        org_id=org_id,
        job_type=job_type,
        status="running",
        celery_task_id=celery_task_id,
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()
    return job


def _complete_job(db, job: ProcessingJob, metrics: Dict[str, Any]) -> None:
    job.status = "completed"
    job.completed_at = datetime.now(timezone.utc)
    job.metrics_json = json.dumps(metrics)
    db.add(job)


def _fail_job(db, job: ProcessingJob, error: str) -> None:
    job.status = "failed"
    job.completed_at = datetime.now(timezone.utc)
    job.error_message = error
    db.add(job)


def _simple_chunk_text(text: str, max_tokens: int = 512) -> List[str]:
    """
    Naïve whitespace-based text chunker.
    Splits on words, appending to a chunk until the word-count limit is reached.
    (A proper tokenizer is preferred in production; this avoids a heavy
    dependency inside the Celery worker at import time.)
    """
    words = text.split()
    chunks: List[str] = []
    current: List[str] = []
    for word in words:
        current.append(word)
        if len(current) >= max_tokens:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks or [text]


# ---------------------------------------------------------------------------
# Task 1: docling_parse_task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="backend.app.tasks.ocr_tasks.docling_parse_task",
    bind=True,
    max_retries=3,
    autoretry_for=(botocore.exceptions.ClientError, botocore.exceptions.ConnectionError, ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    on_failure=handle_task_failure,
)
@tracer.start_as_current_span("docling_parse_task")
def docling_parse_task(self, document_id: str) -> Dict[str, Any]:
    """
    Downloads the PDF from S3, runs Docling structure-aware parsing,
    and bulk-inserts DocumentParseElement rows.
    """
    logger.info(f"[docling_parse_task] Starting for document {document_id}")
    doc_uuid = uuid.UUID(document_id)

    db = SessionLocal()
    temp_dir = tempfile.mkdtemp()
    job = None
    try:
        doc = document_repo.get(db, id=doc_uuid)
        if not doc:
            return {"status": "skipped", "reason": "document_not_found"}

        job = _create_job(db, doc.id, doc.org_id, "docling_parse", self.request.id or "")
        db.commit()

        # Sprint 10: Deduplication — skip Docling if an identical file already exists
        from backend.app.services.storage_optimizer import find_completed_duplicate
        dup_doc = find_completed_duplicate(db, document_repo.model, doc.file_hash or "", doc.id)
        if dup_doc:
            logger.info(
                "[docling_parse_task] Duplicate of %s detected. Copying %d parse elements.",
                dup_doc.id, 0,
            )
            existing_elements = db.query(DocumentParseElement).filter(
                DocumentParseElement.document_id == dup_doc.id
            ).all()
            if existing_elements:
                copied = [
                    DocumentParseElement(
                        id=uuid.uuid4(),
                        document_id=doc_uuid,
                        org_id=doc.org_id,
                        page_number=e.page_number,
                        element_type=e.element_type,
                        content=e.content,
                        reading_order=e.reading_order,
                        bbox_x0=e.bbox_x0,
                        bbox_y0=e.bbox_y0,
                        bbox_x1=e.bbox_x1,
                        bbox_y1=e.bbox_y1,
                    )
                    for e in existing_elements
                ]
                db.bulk_save_objects(copied)
                _complete_job(db, job, {"elements_created": len(copied), "deduplicated": True})
                db.commit()
                logger.info("[docling_parse_task] Copied %d parse elements from duplicate.", len(copied))
                return {"status": "completed", "elements_created": len(copied), "deduplicated": True}

        pdf_s3_key = doc.storage_path
        if doc.file_type.lower() not in ["pdf", "png", "jpg", "jpeg"]:
            pdf_s3_key = f"{os.path.splitext(doc.storage_path)[0]}.pdf"

        local_path = os.path.join(temp_dir, f"document.{doc.file_type.lower()}")
        try:
            s3_storage.client.download_file(s3_storage.bucket_name, pdf_s3_key, local_path)
        except Exception as dl_err:
            logger.error(f"[docling_parse_task] S3 download failed: {dl_err}")
            raise

        # Run Docling parser
        from backend.app.services.docling_service import get_docling_service
        svc = get_docling_service()
        result = svc.parse_document(local_path, doc.file_type.lower())

        if not result.success:
            raise RuntimeError(f"Docling parse failed: {result.error}")

        # Delete existing parse elements for this document (idempotent re-run)
        db.query(DocumentParseElement).filter(
            DocumentParseElement.document_id == doc_uuid
        ).delete(synchronize_session=False)

        # Bulk insert
        elements_created = 0
        new_elements = []
        for elem in result.elements:
            if not elem.content and elem.element_type not in ("image", "figure"):
                continue
            new_elements.append(DocumentParseElement(
                id=uuid.uuid4(),
                document_id=doc_uuid,
                org_id=doc.org_id,
                page_number=elem.page_number,
                element_type=elem.element_type,
                content=elem.content,
                reading_order=elem.reading_order,
                bbox_x0=elem.bbox_x0,
                bbox_y0=elem.bbox_y0,
                bbox_x1=elem.bbox_x1,
                bbox_y1=elem.bbox_y1,
            ))
            elements_created += 1
        
        if new_elements:
            db.bulk_save_objects(new_elements)

        metrics = {
            "elements_created": elements_created,
            "page_count": result.page_count,
        }
        _complete_job(db, job, metrics)
        db.commit()

        logger.info(
            f"[docling_parse_task] Completed for {document_id}: "
            f"{elements_created} elements across {result.page_count} pages."
        )
        return {"status": "completed", "elements_created": elements_created}

    except Exception as exc:
        if job:
            _fail_job(db, job, str(exc))
            try:
                db.commit()
            except Exception:
                pass
        db.close()
        raise
    finally:
        db.close()
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Task 2: ocr_task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="backend.app.tasks.ocr_tasks.ocr_task",
    bind=True,
    max_retries=3,
    autoretry_for=(botocore.exceptions.ClientError, botocore.exceptions.ConnectionError, ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    on_failure=handle_task_failure,
)
@tracer.start_as_current_span("ocr_task")
def ocr_task(self, document_id: str) -> Dict[str, Any]:
    """
    For each page flagged as scanned (embedded text < threshold), downloads the
    rendered PNG from S3, runs PaddleOCR, and bulk-inserts OcrChunk rows.
    """
    logger.info(f"[ocr_task] Starting for document {document_id}")
    doc_uuid = uuid.UUID(document_id)

    db = SessionLocal()
    temp_dir = tempfile.mkdtemp()
    job = None
    try:
        doc = document_repo.get(db, id=doc_uuid)
        if not doc:
            return {"status": "skipped", "reason": "document_not_found"}

        job = _create_job(db, doc.id, doc.org_id, "ocr", self.request.id or "")
        db.commit()

        # Sprint 10: Deduplication — copy OCR chunks from identical document
        from backend.app.services.storage_optimizer import find_completed_duplicate
        dup_doc = find_completed_duplicate(db, document_repo.model, doc.file_hash or "", doc.id)
        if dup_doc:
            logger.info("[ocr_task] Duplicate of %s detected. Copying OCR chunks.", dup_doc.id)
            existing_chunks = db.query(OcrChunk).filter(OcrChunk.document_id == dup_doc.id).all()
            if existing_chunks:
                copied = [
                    OcrChunk(
                        document_id=doc_uuid,
                        org_id=doc.org_id,
                        page_number=c.page_number,
                        text=c.text,
                        confidence=c.confidence,
                        language=c.language,
                        bbox_x0=c.bbox_x0,
                        bbox_y0=c.bbox_y0,
                        bbox_x1=c.bbox_x1,
                        bbox_y1=c.bbox_y1,
                        reading_order=c.reading_order,
                    )
                    for c in existing_chunks
                ]
                db.bulk_save_objects(copied)
                _complete_job(db, job, {"chunks_created": len(copied), "deduplicated": True})
                db.commit()
                logger.info("[ocr_task] Copied %d OCR chunks from duplicate.", len(copied))
                return {"status": "completed", "chunks_created": len(copied), "deduplicated": True}

        ocr_svc = get_ocr_service()

        pages = document_page_repo.get_by_document(db, document_id=doc_uuid)
        total_chunks = 0
        pages_processed = 0

        # Delete existing OCR chunks (idempotent)
        db.query(OcrChunk).filter(
            OcrChunk.document_id == doc_uuid
        ).delete(synchronize_session=False)
        db.flush()

        with StageProfiler(db, doc_uuid, doc.org_id, "ocr"):
            scanned_pages = [p for p in pages if ocr_svc.is_scanned_page(p.text_content)]
            if scanned_pages:
                def download_png(page):
                    png_local = os.path.join(temp_dir, f"page_{page.page_number}.png")
                    try:
                        s3_storage.client.download_file(
                            s3_storage.bucket_name, page.png_storage_path, png_local
                        )
                        return (page.page_number, png_local)
                    except Exception as err:
                        logger.warning(f"[ocr_task] Download failed: {err}")
                        return None
                
                # Parallel S3 Downloads
                batch_png_paths = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    results = executor.map(download_png, scanned_pages)
                    for res in results:
                        if res:
                            batch_png_paths.append(res)
                
                # Sequential OCR
                all_new_chunks = []
                for page_num, png_local in batch_png_paths:
                    results = ocr_svc.run_page_ocr(png_local)
                    for chunk in results:
                        all_new_chunks.append(OcrChunk(
                            document_id=doc_uuid,
                            org_id=doc.org_id,
                            page_number=page_num,
                            text=chunk.text,
                            confidence=chunk.confidence,
                            language=chunk.language,
                            bbox_x0=chunk.bbox_x0,
                            bbox_y0=chunk.bbox_y0,
                            bbox_x1=chunk.bbox_x1,
                            bbox_y1=chunk.bbox_y1,
                            reading_order=chunk.reading_order,
                        ))
                    pages_processed += 1
                
                if all_new_chunks:
                    db.bulk_save_objects(all_new_chunks)
                    db.flush()
                    total_chunks = len(all_new_chunks)
        logger.info(f"[ocr_task] OCR chunks generated: {total_chunks}")

        metrics = {
            "pages_processed": pages_processed,
            "chunks_created": total_chunks,
        }
        _complete_job(db, job, metrics)
        db.commit()

        logger.info(
            f"[ocr_task] Completed for {document_id}: "
            f"{total_chunks} chunks across {pages_processed} scanned pages."
        )
        return {"status": "completed", "pages_processed": pages_processed, "chunks_created": total_chunks}

    except Exception as exc:
        if job:
            _fail_job(db, job, str(exc))
            try:
                db.commit()
            except Exception:
                pass
        db.close()
        raise
    finally:
        db.close()
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Task 3: bge_embed_task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="backend.app.tasks.ocr_tasks.bge_embed_task",
    bind=True,
    max_retries=3,
    autoretry_for=(botocore.exceptions.ClientError, botocore.exceptions.ConnectionError, ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    on_failure=handle_task_failure,
)
@tracer.start_as_current_span("bge_embed_task")
def bge_embed_task(self, document_id: str) -> Dict[str, Any]:
    """
    Reads DocumentParseElement and OcrChunk rows, chunks text to ≤512 tokens,
    encodes via BGE-M3, and upserts to Qdrant 'text_chunks' with full RBAC payload.
    Persists TextEmbeddingChunk rows with qdrant_point_id pointers.
    """
    logger.info(f"[bge_embed_task] Starting for document {document_id}")
    doc_uuid = uuid.UUID(document_id)

    db = SessionLocal()
    job = None
    try:
        doc = document_repo.get(db, id=doc_uuid)
        if not doc:
            return {"status": "skipped", "reason": "document_not_found"}

        job = _create_job(db, doc.id, doc.org_id, "bge_embed", self.request.id or "")
        db.commit()

        org_id = str(doc.org_id)
        folder_id = str(doc.folder_id) if doc.folder_id else None

        from backend.app.services.bge_service import get_bge_service
        bge = get_bge_service()
        from backend.app.core.qdrant import qdrant_client
        from qdrant_client.models import PointStruct

        # 1. Deduplication Check — reuse ORIGINAL Qdrant point IDs (zero new vectors)
        if doc.file_hash:
            duplicate_doc = db.query(document_repo.model).filter(
                document_repo.model.file_hash == doc.file_hash,
                document_repo.model.status == "completed",
                document_repo.model.id != doc.id
            ).first()

            if duplicate_doc:
                logger.info(
                    "[bge_embed_task] Duplicate of %s detected. Reusing original Qdrant point IDs "
                    "(zero new vectors written).",
                    duplicate_doc.id,
                )
                dup_chunks = db.query(TextEmbeddingChunk).filter(
                    TextEmbeddingChunk.document_id == duplicate_doc.id
                ).all()

                if dup_chunks:
                    # Point new DB rows at the SAME Qdrant point IDs — no upsert needed
                    new_db_chunks = [
                        TextEmbeddingChunk(
                            document_id=doc_uuid,
                            org_id=doc.org_id,
                            folder_id=doc.folder_id,
                            page_number=orig.page_number,
                            chunk_index=orig.chunk_index,
                            chunk_type=orig.chunk_type,
                            content=orig.content,
                            section=orig.section,
                            heading=orig.heading,
                            hierarchy=orig.hierarchy,
                            parent_section=orig.parent_section,
                            qdrant_point_id=orig.qdrant_point_id,  # reuse same point
                            language=orig.language,
                            version=orig.version,
                        )
                        for orig in dup_chunks
                    ]
                    db.bulk_save_objects(new_db_chunks)
                    db.commit()
                    _complete_job(db, job, {"chunks_created": len(new_db_chunks), "deduplicated": True, "new_qdrant_points": 0})
                    return {"status": "completed", "chunks_created": len(new_db_chunks), "deduplicated": True, "new_qdrant_points": 0}

        # 2. Extract DocumentType for semantic chunker
        from backend.app.models.models import DocumentSummary
        doc_summary = db.query(DocumentSummary).filter(DocumentSummary.document_id == doc_uuid).first()
        doc_type = doc_summary.document_type if doc_summary else None

        # Gather all text units to embed
        with StageProfiler(db, doc_uuid, doc.org_id, "embedding"):
            parse_elements = db.query(DocumentParseElement).filter(
                DocumentParseElement.document_id == doc_uuid,
                DocumentParseElement.element_type.in_(["paragraph", "heading", "table", "list", "caption"])
            ).order_by(DocumentParseElement.page_number, DocumentParseElement.reading_order).all()

            ocr_chunks = db.query(OcrChunk).filter(OcrChunk.document_id == doc_uuid).order_by(OcrChunk.page_number, OcrChunk.reading_order).all()

            all_elements = list(parse_elements) + list(ocr_chunks)

            from backend.app.services.semantic_chunker import SemanticChunkEngine
            chunk_engine = SemanticChunkEngine(document_type=doc_type)
            semantic_chunks = chunk_engine.process_elements(all_elements)

            if not semantic_chunks:
                logger.info(f"[bge_embed_task] No text to embed for document {document_id}. Skipping.")
                _complete_job(db, job, {"chunks_created": 0})
                db.commit()
                return {"status": "completed", "chunks_created": 0}

            # Delete existing text embedding chunks (idempotent)
            try:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                qdrant_client.delete(
                    collection_name=settings.QDRANT_TEXT_COLLECTION_NAME,
                    points_selector=Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]),
                )
            except Exception as qd_err:
                logger.warning(f"[bge_embed_task] Qdrant delete failed (non-fatal): {qd_err}")

            db.query(TextEmbeddingChunk).filter(
                TextEmbeddingChunk.document_id == doc_uuid
            ).delete(synchronize_session=False)
            db.flush()

            batch_size = 32
            db_chunks = []
            qdrant_points = []
            chunks_created = 0

            for i in range(0, len(semantic_chunks), batch_size):
                batch_chunks = semantic_chunks[i: i + batch_size]
                texts_only = [c.content for c in batch_chunks]
                vectors = bge.encode_texts(texts_only, batch_size=batch_size)

                for chunk, vector in zip(batch_chunks, vectors):
                    qdrant_point_id = str(uuid.uuid4())
                    payload = {
                        "org_id": org_id,
                        "folder_id": folder_id,
                        "document_id": document_id,
                        "page_number": chunk.page_number,
                        "chunk_type": chunk.chunk_type,
                        "language": "en",
                        "content": chunk.content[:1000],  # payload snippet
                        "section": chunk.section,
                        "heading": chunk.heading,
                        "hierarchy": chunk.hierarchy,
                        "parent_section": chunk.parent_section,
                        "version": 1,
                    }
                    qdrant_points.append(
                        PointStruct(
                            id=qdrant_point_id,
                            vector=vector,
                            payload=payload,
                        )
                    )
                    db_chunks.append(TextEmbeddingChunk(
                        id=uuid.uuid4(),
                        document_id=doc_uuid,
                        org_id=doc.org_id,
                        folder_id=doc.folder_id,
                        page_number=chunk.page_number,
                        chunk_index=chunks_created,
                        chunk_type=chunk.chunk_type,
                        content=chunk.content,
                        section=chunk.section,
                        heading=chunk.heading,
                        hierarchy=chunk.hierarchy,
                        parent_section=chunk.parent_section,
                        qdrant_point_id=uuid.UUID(qdrant_point_id),
                        language="en",
                        version=1,
                    ))
                    chunks_created += 1
            
            if db_chunks:
                db.bulk_save_objects(db_chunks)

            # Upsert to Qdrant in batches of 100
            q_batch_size = 100
            for i in range(0, len(qdrant_points), q_batch_size):
                batch = qdrant_points[i: i + q_batch_size]
                try:
                    qdrant_client.upsert(
                        collection_name=settings.QDRANT_TEXT_COLLECTION_NAME,
                        points=batch,
                    )
                except Exception as qd_err:
                    logger.warning(
                        f"[bge_embed_task] Qdrant upsert batch {i}-{i+q_batch_size} failed: {qd_err}. "
                        "Continuing (dev fallback)."
                    )

            metrics = {"chunks_created": chunks_created, "qdrant_points": len(qdrant_points)}
            _complete_job(db, job, metrics)
            db.commit()

            logger.info(
                f"[bge_embed_task] Completed for {document_id}: "
                f"{chunks_created} chunks embedded."
            )
            return {"status": "completed", "chunks_created": chunks_created}

    except Exception as exc:
        if job:
            _fail_job(db, job, str(exc))
            try:
                db.commit()
            except Exception:
                pass
        db.close()
        raise
    finally:
        db.close()


    # ---------------------------------------------------------------------------
    # Task 4: metadata_enrichment_task
    # ---------------------------------------------------------------------------

@celery_app.task(
    name="backend.app.tasks.ocr_tasks.metadata_enrichment_task",
    bind=True,
    max_retries=3,
    autoretry_for=(botocore.exceptions.ClientError, botocore.exceptions.ConnectionError, ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    on_failure=handle_task_failure,
)
@tracer.start_as_current_span("metadata_enrichment_task")
def metadata_enrichment_task(self, document_id: str) -> Dict[str, Any]:
    """
    Collects the full document text from DocumentParseElement + OcrChunk rows,
    calls Gemini Flash for metadata, and persists to the summary/keyword/entity tables.
    Also updates Document.category and Document.department.
    """
    logger.info(f"[metadata_enrichment_task] Starting for document {document_id}")
    doc_uuid = uuid.UUID(document_id)

    db = SessionLocal()
    job = None
    try:
        doc = document_repo.get(db, id=doc_uuid)
        if not doc:
            return {"status": "skipped", "reason": "document_not_found"}

        job = _create_job(db, doc.id, doc.org_id, "metadata_enrichment", self.request.id or "")
        db.commit()

        # Sprint 10: Metadata dedup — copy from identical file, skip Gemini entirely
        from backend.app.services.storage_optimizer import find_completed_duplicate
        from backend.app.core.cache import get_cache, set_cache, generate_cache_key
        from backend.app.models.models import (
            DocumentSummary, DocumentKeyword, DocumentEntity
        )

        dup_doc = find_completed_duplicate(db, document_repo.model, doc.file_hash or "", doc.id)
        if dup_doc:
            logger.info("[metadata_enrichment_task] Duplicate of %s. Copying metadata.", dup_doc.id)
            dup_summary = db.query(DocumentSummary).filter(DocumentSummary.document_id == dup_doc.id).first()
            dup_keywords = db.query(DocumentKeyword).filter(DocumentKeyword.document_id == dup_doc.id).all()
            dup_entities = db.query(DocumentEntity).filter(DocumentEntity.document_id == dup_doc.id).all()

            if dup_summary:
                db.query(DocumentSummary).filter(DocumentSummary.document_id == doc_uuid).delete(synchronize_session=False)
                new_summary = DocumentSummary(
                    document_id=doc_uuid,
                    org_id=doc.org_id,
                    summary=dup_summary.summary,
                    document_type=dup_summary.document_type,
                    language=dup_summary.language,
                    topics_json=dup_summary.topics_json,
                    entities_json=dup_summary.entities_json,
                    key_dates_json=dup_summary.key_dates_json,
                    confidence_score=dup_summary.confidence_score,
                )
                db.add(new_summary)

            if dup_keywords:
                db.query(DocumentKeyword).filter(DocumentKeyword.document_id == doc_uuid).delete(synchronize_session=False)
                db.bulk_save_objects([
                    DocumentKeyword(document_id=doc_uuid, org_id=doc.org_id, keyword=k.keyword, score=k.score)
                    for k in dup_keywords
                ])

            if dup_entities:
                db.query(DocumentEntity).filter(DocumentEntity.document_id == doc_uuid).delete(synchronize_session=False)
                db.bulk_save_objects([
                    DocumentEntity(document_id=doc_uuid, org_id=doc.org_id, entity_type=e.entity_type, entity_value=e.entity_value, confidence=e.confidence)
                    for e in dup_entities
                ])

            doc.category = dup_doc.category
            doc.department = dup_doc.department
            _complete_job(db, job, {"deduplicated": True})
            db.commit()
            return {"status": "completed", "deduplicated": True}

        # Sprint 10: Metadata cache — check Redis before calling Gemini
        meta_cache_key = generate_cache_key("metadata", file_hash=doc.file_hash or doc.name)
        cached_meta = get_cache(meta_cache_key)
        if cached_meta:
            logger.info("[metadata_enrichment_task] Cache HIT for %s", doc.file_hash)
            # Restore cached metadata into DB
            from backend.app.services.metadata_service import enrich_document_metadata
            from backend.app.models.models import DocumentSummary
            db.query(DocumentSummary).filter(DocumentSummary.document_id == doc_uuid).delete(synchronize_session=False)
            summary_data = cached_meta.get("summary", {})
            if summary_data:
                db.add(DocumentSummary(
                    document_id=doc_uuid,
                    org_id=doc.org_id,
                    summary=summary_data.get("summary", ""),
                    document_type=summary_data.get("document_type", ""),
                    language=summary_data.get("language", ""),
                    topics_json=summary_data.get("topics_json"),
                    entities_json=summary_data.get("entities_json"),
                    key_dates_json=summary_data.get("key_dates_json"),
                    confidence_score=summary_data.get("confidence_score", 0.0),
                ))
            _complete_job(db, job, {"cache_hit": True})
            db.commit()
            return {"status": "completed", "cache_hit": True}

        parse_texts = (
            db.query(DocumentParseElement.content)
            .filter(
                DocumentParseElement.document_id == doc_uuid,
                DocumentParseElement.content.isnot(None),
            )
            .order_by(DocumentParseElement.page_number, DocumentParseElement.reading_order)
            .all()
        )
        ocr_texts = (
            db.query(OcrChunk.text)
            .filter(OcrChunk.document_id == doc_uuid)
            .order_by(OcrChunk.page_number, OcrChunk.reading_order)
            .all()
        )

        full_text_parts = [r[0] for r in parse_texts if r[0]] + [r[0] for r in ocr_texts if r[0]]

        if not full_text_parts:
            logger.info(f"[metadata_enrichment_task] No DB text found for {document_id}, using PyMuPDF direct extraction.")
            # Use PyMuPDF to extract text directly from the PDF for fast metadata extraction
            pdf_s3_key = doc.storage_path
            if doc.file_type.lower() not in ["pdf", "png", "jpg", "jpeg"]:
                pdf_s3_key = f"{os.path.splitext(doc.storage_path)[0]}.pdf"
            
            temp_dir = tempfile.mkdtemp()
            local_path = os.path.join(temp_dir, f"doc_{doc_uuid}.pdf")
            try:
                s3_storage.client.download_file(s3_storage.bucket_name, pdf_s3_key, local_path)
                import fitz
                with fitz.open(local_path) as pdf_doc:
                    for page in pdf_doc:
                        text = page.get_text("text")
                        if text:
                            full_text_parts.append(text)
            except Exception as e:
                logger.error(f"[metadata_enrichment_task] PyMuPDF extraction failed: {e}")
            finally:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)

        # Fallback to page text_content if still no structured text available
        if not full_text_parts:
            pages = document_page_repo.get_by_document(db, document_id=doc_uuid)
            full_text_parts = [p.text_content for p in pages if p.text_content]

        full_text = " ".join(full_text_parts)

        from backend.app.services.metadata_service import enrich_document_metadata
        success = asyncio.run(
            enrich_document_metadata(
                db=db,
                document_id=document_id,
                full_text=full_text,
                org_id=str(doc.org_id),
            )
        )

        # Sprint 10: Cache the metadata result for 24h
        if success:
            from backend.app.models.models import DocumentSummary as DS
            saved_summary = db.query(DS).filter(DS.document_id == doc_uuid).first()
            if saved_summary:
                set_cache(meta_cache_key, {"summary": {
                    "summary": saved_summary.summary,
                    "document_type": saved_summary.document_type,
                    "language": saved_summary.language,
                    "topics_json": saved_summary.topics_json,
                    "entities_json": saved_summary.entities_json,
                    "key_dates_json": saved_summary.key_dates_json,
                    "confidence_score": saved_summary.confidence_score,
                }})  # TTL: 86400s from cache.py prefix rules
        _complete_job(db, job, metrics)
        db.commit()
        
        logger.info(f"[metadata_enrichment_task] Completed for {document_id}: success={success}")
        
        # Trigger Sprint 5 Knowledge Graph build
        if success:
            try:
                from backend.app.tasks.knowledge_graph_tasks import build_knowledge_graph_task
                build_knowledge_graph_task.delay(document_id)
            except Exception as e:
                logger.error(f"Failed to trigger knowledge graph task: {e}")
                
        return {"status": "completed", "success": success}

    except Exception as exc:
        if job:
            _fail_job(db, job, str(exc))
            try:
                db.commit()
            except Exception:
                pass
        raise
    finally:
        db.close()

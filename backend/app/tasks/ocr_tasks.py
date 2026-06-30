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

        # Determine S3 key (prefer PDF if available)
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
        for elem in result.elements:
            if not elem.content and elem.element_type not in ("image", "figure"):
                continue
            db.add(DocumentParseElement(
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

        from backend.app.services.ocr_service import get_ocr_service
        ocr_svc = get_ocr_service()

        pages = document_page_repo.get_by_document(db, document_id=doc_uuid)
        total_chunks = 0
        pages_processed = 0

        # Delete existing OCR chunks (idempotent)
        db.query(OcrChunk).filter(
            OcrChunk.document_id == doc_uuid
        ).delete(synchronize_session=False)
        db.flush()

        batch_size = 4
        all_new_chunks = []
        
        for i in range(0, len(pages), batch_size):
            batch_pages = pages[i:i+batch_size]
            scanned_pages = [p for p in batch_pages if not ocr_svc.is_scanned_page(p.text_content)]
            if not scanned_pages:
                continue

            # Batch Download
            t0_dl = time.time()
            batch_png_paths = []
            for page in scanned_pages:
                png_local = os.path.join(temp_dir, f"page_{page.page_number}.png")
                try:
                    s3_storage.client.download_file(
                        s3_storage.bucket_name, page.png_storage_path, png_local
                    )
                    batch_png_paths.append((page.page_number, png_local))
                except Exception as dl_err:
                    logger.warning(
                        f"[ocr_task] Failed to download page {page.page_number} PNG: {dl_err}. Skipping."
                    )
            t_dl = time.time() - t0_dl
            
            if not batch_png_paths:
                continue
            
            # Batch OCR
            t0_ocr = time.time()
            # We map page_paths to their real page numbers for DB tracking
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
            t_ocr = time.time() - t0_ocr
            logger.info(f"[ocr_task] Batch times for {len(batch_png_paths)} pages: Download {t_dl:.2f}s, OCR {t_ocr:.2f}s")

        t0_db = time.time()
        if all_new_chunks:
            db.add_all(all_new_chunks)
            db.flush()
            total_chunks = len(all_new_chunks)
        t_db = time.time() - t0_db
        logger.info(f"[ocr_task] DB Bulk Insert time for {total_chunks} chunks: {t_db:.2f}s")

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

        # Gather all text units to embed
        # Source 1: Docling parse elements (paragraphs, headings, tables)
        parse_elements = (
            db.query(DocumentParseElement)
            .filter(
                DocumentParseElement.document_id == doc_uuid,
                DocumentParseElement.element_type.in_(
                    ["paragraph", "heading", "table", "list", "caption"]
                ),
            )
            .order_by(DocumentParseElement.page_number, DocumentParseElement.reading_order)
            .all()
        )

        # Source 2: OCR chunks
        ocr_chunks = (
            db.query(OcrChunk)
            .filter(OcrChunk.document_id == doc_uuid)
            .order_by(OcrChunk.page_number, OcrChunk.reading_order)
            .all()
        )

        # Build a flat list of (raw_text, page_number, chunk_type, language) tuples
        text_units: List[tuple] = []
        for elem in parse_elements:
            if elem.content and elem.content.strip():
                sub_chunks = _simple_chunk_text(elem.content, settings.BGE_M3_MAX_TOKENS)
                for sc in sub_chunks:
                    text_units.append((sc, elem.page_number, elem.element_type, None))

        for oc in ocr_chunks:
            if oc.text and oc.text.strip():
                sub_chunks = _simple_chunk_text(oc.text, settings.BGE_M3_MAX_TOKENS)
                for sc in sub_chunks:
                    text_units.append((sc, oc.page_number, "ocr", oc.language))

        if not text_units:
            logger.info(f"[bge_embed_task] No text to embed for document {document_id}. Skipping.")
            _complete_job(db, job, {"chunks_created": 0})
            db.commit()
            return {"status": "completed", "chunks_created": 0}

        # Delete existing text embedding chunks (idempotent)
        # Also delete from Qdrant
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            qdrant_client.delete(
                collection_name=settings.QDRANT_TEXT_COLLECTION_NAME,
                points_selector=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                ),
            )
        except Exception as qd_err:
            logger.warning(f"[bge_embed_task] Qdrant delete failed (non-fatal): {qd_err}")

        db.query(TextEmbeddingChunk).filter(
            TextEmbeddingChunk.document_id == doc_uuid
        ).delete(synchronize_session=False)
        db.flush()

        # Batch-encode all text units
        texts_only = [t[0] for t in text_units]
        vectors = bge.encode_texts(texts_only, batch_size=settings.BGE_M3_BATCH_SIZE)

        qdrant_points: List[PointStruct] = []
        chunks_created = 0
        for chunk_index, ((text, page_number, chunk_type, language), vector) in enumerate(
            zip(text_units, vectors)
        ):
            qdrant_point_id = str(uuid.uuid4())
            qdrant_points.append(
                PointStruct(
                    id=qdrant_point_id,
                    vector=vector,
                    payload={
                        "org_id": org_id,
                        "folder_id": folder_id,
                        "document_id": document_id,
                        "page_number": page_number,
                        "chunk_type": chunk_type,
                        "language": language or "en",
                        "content": text[:1000],  # payload snippet for display
                        "version": 1,
                    },
                )
            )
            db.add(TextEmbeddingChunk(
                document_id=doc_uuid,
                org_id=doc.org_id,
                folder_id=doc.folder_id,
                page_number=page_number,
                chunk_index=chunk_index,
                chunk_type=chunk_type,
                content=text,
                qdrant_point_id=uuid.UUID(qdrant_point_id),
                language=language,
                version=1,
            ))
            chunks_created += 1

        # Upsert to Qdrant in batches of 100
        batch_size = 100
        for i in range(0, len(qdrant_points), batch_size):
            batch = qdrant_points[i: i + batch_size]
            try:
                qdrant_client.upsert(
                    collection_name=settings.QDRANT_TEXT_COLLECTION_NAME,
                    points=batch,
                )
            except Exception as qd_err:
                logger.warning(
                    f"[bge_embed_task] Qdrant upsert batch {i}-{i+batch_size} failed: {qd_err}. "
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

        # Build full text from parse elements + OCR chunks
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

        # Fallback to page text_content if no structured text available
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

        metrics = {"success": success, "text_length": len(full_text)}
        _complete_job(db, job, metrics)
        db.commit()

        logger.info(f"[metadata_enrichment_task] Completed for {document_id}: success={success}")
        return {"status": "completed", "success": success}

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

import os
import uuid
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from celery import chain
import time

from backend.app.api.deps import get_current_user_context, CurrentUserContext, PermissionChecker
from backend.app.core.db import get_db
from backend.app.core.s3 import s3_storage
from backend.app.repositories.base_repo import document_repo
from backend.app.models.models import DocumentPage, OcrChunk, DocumentSummary, DocumentKeyword, DocumentEntity
from backend.app.services.validation import validate_file_size, validate_file_type, ValidationError
from backend.app.tasks.tasks import scan_malware_task, convert_to_pdf_task, render_pages_task, embed_and_index_task
from backend.app.tasks.ocr_tasks import docling_parse_task, ocr_task, bge_embed_task, metadata_enrichment_task
from backend.app.schemas.schemas import OcrChunkResponse, DocumentMetadataResponse, KeywordResponse, EntityResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Pydantic Schemas ---
class DocumentResponse(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    folder_id: Optional[uuid.UUID]
    name: str
    storage_path: str
    status: str
    file_type: str
    file_size: int
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DocumentUpdate(BaseModel):
    name: Optional[str] = None
    folder_id: Optional[uuid.UUID] = None


# --- Endpoints ---

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    folder_id: Optional[str] = Form(None),
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:write")),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/documents/upload
    Uploads a document to S3, registers it in PostgreSQL, and schedules the Celery ingestion pipeline.
    """
    try:
        folder_uuid = uuid.UUID(folder_id) if folder_id else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid folder_id format.")

    # 1. Read file content for validation
    file_bytes = await file.read()
    file_size = len(file_bytes)

    try:
        # Validate file size
        validate_file_size(file_size)
        # Validate file magic numbers
        ext = validate_file_type(file_bytes)
    except ValidationError as val_err:
        raise HTTPException(status_code=422, detail=val_err.message)

    # Reset file cursor for uploading
    await file.seek(0)

    # 2. Setup document metadata
    doc_id = uuid.uuid4()
    # Path: org_id/doc_id/file_name
    s3_key = f"{current_context.org_id}/{doc_id}/{file.filename}"

    # 3. Upload to S3
    t0_s3 = time.time()
    uploaded = s3_storage.upload_fileobj(file.file, s3_key)
    if not uploaded:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload file to storage."
        )
    logger.info(f"S3 Upload took {time.time() - t0_s3:.2f}s")

    # 4. Save record to PostgreSQL database
    t0_db = time.time()
    doc_in = {
        "id": doc_id,
        "org_id": uuid.UUID(current_context.org_id),
        "folder_id": folder_uuid,
        "name": file.filename,
        "storage_path": s3_key,
        "status": "queued",
        "file_type": ext,
        "file_size": file_size
    }

    try:
        db_doc = document_repo.create(db, obj_in=doc_in)
        # Log storage size usage metric
        from backend.app.services.metrics_service import log_usage_metric
        log_usage_metric(
            db,
            org_id=uuid.UUID(current_context.org_id),
            metric_type="storage_bytes",
            value=float(file_size),
            metadata={"document_id": str(doc_id)}
        )
        logger.info(f"Database insertion took {time.time() - t0_db:.2f}s")
    except Exception as e:
        logger.error(f"Failed to create document in database: {e}")
        # Clean up uploaded S3 object on DB error
        try:
            s3_storage.client.delete_object(Bucket=s3_storage.bucket_name, Key=s3_key)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Failed to save document record.")


    # 5. Trigger the Celery Ingestion Pipeline
    # chain: scan_malware -> convert_to_pdf -> render_pages -> embed_and_index
    try:
        chain(
            scan_malware_task.s(str(doc_id), s3_key),
            convert_to_pdf_task.s(str(doc_id)),
            render_pages_task.s(str(doc_id)),
            embed_and_index_task.s(str(doc_id))
        ).apply_async()
        logger.info(f"Scheduled ingestion pipeline for document {doc_id}.")
    except Exception as exc:
        logger.error(f"Failed to start ingestion pipeline: {exc}")
        # Do not fail request; status remains queued and can be retried or shows queue failure

    return db_doc


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    folder_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents
    Lists all documents belonging to the user's organization. Supports optional folder filtering.
    """
    query = db.query(document_repo.model).filter(document_repo.model.org_id == uuid.UUID(current_context.org_id))
    if folder_id:
        if folder_id.lower() == "root":
            query = query.filter(document_repo.model.folder_id == None)
        else:
            try:
                query = query.filter(document_repo.model.folder_id == uuid.UUID(folder_id))
            except ValueError:
                pass
    
    query = query.order_by(document_repo.model.created_at.desc())
    docs = query.offset(skip).limit(limit).all()
    return docs


@router.get("/processing", response_model=List[DocumentResponse])
def get_processing_documents(
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/processing
    Retrieves all documents currently in queued, processing, or failed state for the organization.
    """
    docs = db.query(document_repo.model).filter(
        document_repo.model.org_id == uuid.UUID(current_context.org_id),
        document_repo.model.status.in_(["queued", "processing", "failed"])
    ).order_by(document_repo.model.created_at.desc()).all()
    return docs


@router.patch("/{doc_id}", response_model=DocumentResponse)
def update_document(
    doc_id: uuid.UUID,
    payload: DocumentUpdate,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:write")),
    db: Session = Depends(get_db)
):
    """
    PATCH /api/v1/documents/{doc_id}
    Updates document details (such as name or parent folder).
    """
    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=403, detail="Cross-tenant edit not allowed.")

    obj_in = payload.model_dump(exclude_unset=True)
    updated_doc = document_repo.update(db, db_obj=db_doc, obj_in=obj_in)
    return updated_doc


@router.post("/{doc_id}/retry", response_model=DocumentResponse)
def retry_document(
    doc_id: uuid.UUID,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:write")),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/documents/{doc_id}/retry
    Retries the background ingestion pipeline for a failed document.
    """
    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=403, detail="Cross-tenant edit not allowed.")
        
    if db_doc.status not in ["failed", "queued", "processing"]:
        raise HTTPException(status_code=400, detail="Only failed, queued, or processing documents can be retried.")

    # Reset status
    updated_doc = document_repo.update(
        db, 
        db_obj=db_doc, 
        obj_in={"status": "queued", "error_message": None}
    )

    try:
        chain(
            scan_malware_task.s(str(doc_id), db_doc.storage_path),
            convert_to_pdf_task.s(str(doc_id)),
            render_pages_task.s(str(doc_id)),
            embed_and_index_task.s(str(doc_id))
        ).apply_async()
        logger.info(f"Re-scheduled ingestion pipeline for document {doc_id}.")
    except Exception as exc:
        logger.error(f"Failed to restart ingestion pipeline: {exc}")

    return updated_doc


@router.get("/{doc_id}", response_model=DocumentResponse)
def get_document(
    doc_id: uuid.UUID,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/{doc_id}
    Retrieves document status and details.
    """
    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access not allowed.")

    return db_doc


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: uuid.UUID,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:write")),
    db: Session = Depends(get_db)
):
    """
    DELETE /api/v1/documents/{doc_id}
    Deletes a document from the database, S3 storage, and Qdrant.
    """
    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=403, detail="Cross-tenant deletion not allowed.")

    # 1. Delete matching S3 objects
    try:
        s3_storage.client.delete_object(Bucket=s3_storage.bucket_name, Key=db_doc.storage_path)
        # If there's a converted PDF, delete it too
        if db_doc.file_type.lower() not in ["pdf", "png", "jpg", "jpeg"]:
            pdf_key = f"{os.path.splitext(db_doc.storage_path)[0]}.pdf"
            s3_storage.client.delete_object(Bucket=s3_storage.bucket_name, Key=pdf_key)
    except Exception as s3_err:
        logger.warning(f"Failed to delete S3 objects for doc {doc_id}: {s3_err}")

    # 2. Delete points from Qdrant
    try:
        from backend.app.core.qdrant import qdrant_client
        from backend.app.core.config import settings
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        qdrant_client.delete(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points_selector=Filter(
                must=[
                    FieldCondition(key="document_id", match=MatchValue(value=str(doc_id)))
                ]
            )
        )
    except Exception as qd_err:
        logger.warning(f"Failed to delete Qdrant points for doc {doc_id}: {qd_err}")

    # 3. Delete from database
    document_repo.remove(db, id=doc_id)
    return None


class DocumentPageResponse(BaseModel):
    id: uuid.UUID
    page_number: int
    image_url: str

    class Config:
        from_attributes = True

@router.get("/{doc_id}/pages", response_model=List[DocumentPageResponse])
def get_document_pages(
    doc_id: uuid.UUID,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/{doc_id}/pages
    Retrieves the rendered pages (PNGs) for the document.
    """
    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access not allowed.")

    pages = db.query(DocumentPage).filter(DocumentPage.document_id == doc_id).order_by(DocumentPage.page_number.asc()).all()
    
    response = []
    for page in pages:
        # Generate presigned URL valid for 1 hour (3600 seconds)
        try:
            url = s3_storage.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': s3_storage.bucket_name, 'Key': page.png_storage_path},
                ExpiresIn=3600
            )
            response.append({
                "id": page.id,
                "page_number": page.page_number,
                "image_url": url
            })
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for page {page.id}: {e}")
            
    return response


# ---------------------------------------------------------------------------
# Sprint 5: Hybrid Pipeline Endpoints
# ---------------------------------------------------------------------------

@router.get("/{doc_id}/ocr", response_model=List[OcrChunkResponse])
def get_document_ocr(
    doc_id: uuid.UUID,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/{doc_id}/ocr
    Retrieves PaddleOCR recognized text regions for the document.
    """
    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access not allowed.")

    chunks = db.query(OcrChunk).filter(
        OcrChunk.document_id == doc_id
    ).order_by(OcrChunk.page_number, OcrChunk.reading_order).all()

    return chunks


@router.get("/{doc_id}/metadata", response_model=DocumentMetadataResponse)
def get_document_metadata(
    doc_id: uuid.UUID,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/{doc_id}/metadata
    Retrieves Gemini Flash generated metadata, summary, entities, and keywords.
    """
    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access not allowed.")

    summary_obj = db.query(DocumentSummary).filter(DocumentSummary.document_id == doc_id).first()
    keywords = db.query(DocumentKeyword).filter(DocumentKeyword.document_id == doc_id).order_by(DocumentKeyword.score.desc()).all()
    entities = db.query(DocumentEntity).filter(DocumentEntity.document_id == doc_id).all()

    import json
    topics = []
    if summary_obj and summary_obj.topics_json:
        try:
            topics = json.loads(summary_obj.topics_json)
        except Exception:
            pass

    return DocumentMetadataResponse(
        summary=summary_obj.summary if summary_obj else None,
        reading_time_minutes=summary_obj.reading_time_minutes if summary_obj else None,
        complexity_score=summary_obj.complexity_score if summary_obj else None,
        document_type=summary_obj.document_type if summary_obj else None,
        topics=topics,
        category=db_doc.category,
        department=db_doc.department,
        keywords=[KeywordResponse.model_validate(k) for k in keywords],
        entities=[EntityResponse.model_validate(e) for e in entities],
    )


@router.post("/{doc_id}/reprocess", status_code=status.HTTP_202_ACCEPTED)
def reprocess_document(
    doc_id: uuid.UUID,
    pipeline: str = "hybrid",  # "hybrid" or "vision"
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:write")),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/documents/{doc_id}/reprocess
    Manually triggers either the full ingestion pipeline or just the hybrid pipeline.
    """
    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access not allowed.")

    if pipeline == "hybrid":
        chain(
            docling_parse_task.si(str(doc_id)),
            ocr_task.si(str(doc_id)),
            bge_embed_task.si(str(doc_id)),
            metadata_enrichment_task.si(str(doc_id))
        ).apply_async(queue="ocr-pipeline")
    else:
        document_repo.update_status(db, doc_id=doc_id, status="queued")
        chain(
            scan_malware_task.s(str(doc_id)),
            convert_to_pdf_task.s(),
            render_pages_task.s(),
            embed_and_index_task.s()
        ).apply_async(queue="ingestion")

    return {"status": "reprocessing_started", "pipeline": pipeline}

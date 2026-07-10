import os
import uuid
import logging
import hashlib
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from celery import chain, chord, group
import time

from backend.app.api.deps import get_current_user_context, CurrentUserContext, PermissionChecker, check_document_permission
from backend.app.core.db import get_db
from backend.app.core.s3 import s3_storage
from backend.app.services.document_service import document_service
from backend.app.repositories.base_repo import document_repo
from backend.app.models.models import DocumentPage, OcrChunk, DocumentSummary, DocumentKeyword, DocumentEntity, KnowledgeGraphEdge, UserDocumentInteraction, DocumentLock, DocumentVersion
from backend.app.services.validation import validate_file_size, validate_file_type, ValidationError
from backend.app.services.security_service import generate_signed_download_url, get_document_watermark_config, apply_watermark_to_pdf, upload_bytes_with_sse
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
    is_archived: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DocumentUpdate(BaseModel):
    name: Optional[str] = None
    folder_id: Optional[uuid.UUID] = None


# --- Endpoints ---

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
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
    file_bytes = file.file.read()
    file_size = len(file_bytes)

    try:
        # Validate file size
        validate_file_size(file_size)
        # Validate file magic numbers
        ext = validate_file_type(file_bytes)
    except ValidationError as val_err:
        raise HTTPException(status_code=422, detail=val_err.message)

    # Reset file cursor for uploading
    file.file.seek(0)
    
    # Calculate file hash
    file_hash = hashlib.sha256(file_bytes).hexdigest()

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
        "org_id": uuid.UUID(str(current_context.org_id)),
        "folder_id": folder_uuid,
        "name": file.filename,
        "storage_path": s3_key,
        "status": "queued",
        "file_type": ext,
        "file_size": file_size,
        "file_hash": file_hash
    }

    try:
        db_doc = document_repo.create(db, obj_in=doc_in)
        
        # Sprint 11: Record initial version
        initial_version = DocumentVersion(
            document_id=db_doc.id,
            org_id=db_doc.org_id,
            version_number=1,
            s3_key=s3_key,
            file_size=file_size,
            file_hash=file_hash,
            uploader_id=uuid.UUID(str(current_context.user.id)),
            change_note="Initial upload"
        )
        db.add(initial_version)
        db.commit()

        # Log storage size usage metric
        from backend.app.services.metrics_service import log_usage_metric
        log_usage_metric(
            db,
            org_id=uuid.UUID(str(current_context.org_id)),
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
    from backend.app.services.document_analyzer import DocumentAnalyzer
    from backend.app.core.config import settings

    try:
        analyzer = DocumentAnalyzer(file_bytes=file_bytes, file_name=file.filename, file_type=ext)
        decision = analyzer.analyze()
        logger.info(f"Document {doc_id} analysis decision: {decision.model_dump_json()}")
        # Build ingestion pipeline based on decision
        prep_tasks = []
        if settings.ENABLE_CLAMAV:
            prep_tasks.append(scan_malware_task.s(str(doc_id), s3_key))
            prep_tasks.append(convert_to_pdf_task.s(str(doc_id)))
        else:
            prep_tasks.append(convert_to_pdf_task.s({"status": "clean", "s3_key": s3_key}, str(doc_id)))

        parallel_tasks = []
        
        if decision.run_vision and settings.ENABLE_VISION:
            if decision.run_ocr and settings.ENABLE_OCR:
                vision_branch = chain(render_pages_task.s(str(doc_id)), embed_and_index_task.s(str(doc_id)), ocr_task.si(str(doc_id)))
            else:
                vision_branch = chain(render_pages_task.s(str(doc_id)), embed_and_index_task.s(str(doc_id)))
            parallel_tasks.append(vision_branch)
            
        if decision.run_docling and settings.DOCLING_ENABLED:
            parallel_tasks.append(docling_parse_task.si(str(doc_id)))
            
        parallel_tasks.append(metadata_enrichment_task.si(str(doc_id)))
        
        # Dispatch workflow
        if parallel_tasks:
            workflow = chain(
                *prep_tasks,
                chord(group(*parallel_tasks), bge_embed_task.si(str(doc_id)))
            )
            workflow.apply_async()
            document_repo.update_status(db, doc_id=doc_id, status="queued")
            logger.info(f"Scheduled adaptive ingestion pipeline for document {doc_id}.")
        else:
            logger.warning(f"No pipeline tasks selected for document {doc_id}.")

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
    docs = document_service.get_document_list(db, current_context, folder_id, skip, limit)
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
    docs = document_service.get_processing_documents(db, current_context)
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

    if not check_document_permission(db, str(doc_id), current_context, "write"):
        raise HTTPException(status_code=403, detail="Access denied: write permission required.")

    # Check lock (enterprise versioning feature only)
    from backend.app.core.config import features as _feat_patch
    if _feat_patch.ENABLE_VERSIONING:
        from datetime import datetime, timezone
        lock = db.query(DocumentLock).filter(DocumentLock.document_id == doc_id).first()
        if lock and lock.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            if lock.locked_by != uuid.UUID(current_context.user.id):
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Document is currently locked by another user."
                )

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
        from backend.app.services.document_analyzer import DocumentAnalyzer
        from backend.app.core.config import settings

        s3_obj = s3_storage.client.get_object(Bucket=s3_storage.bucket_name, Key=db_doc.storage_path)
        file_bytes = s3_obj['Body'].read()

        analyzer = DocumentAnalyzer(file_bytes=file_bytes, file_name=db_doc.name, file_type=db_doc.file_type)
        decision = analyzer.analyze()
        logger.info(f"Document {doc_id} analysis decision for retry: {decision.model_dump_json()}")

        pipeline_tasks = []

        if settings.ENABLE_CLAMAV:
            pipeline_tasks.append(scan_malware_task.s(str(doc_id), db_doc.storage_path))
            first_vision_task = convert_to_pdf_task.s(str(doc_id))
        else:
            first_vision_task = convert_to_pdf_task.s({"status": "clean", "s3_key": db_doc.storage_path}, str(doc_id))

        if decision.run_vision and settings.ENABLE_VISION:
            pipeline_tasks.append(first_vision_task)
            pipeline_tasks.append(render_pages_task.s(str(doc_id)))
            pipeline_tasks.append(embed_and_index_task.s(str(doc_id)))

        if decision.run_docling and settings.DOCLING_ENABLED:
            pipeline_tasks.append(docling_parse_task.si(str(doc_id)))
            
        if decision.run_ocr and settings.ENABLE_OCR:
            pipeline_tasks.append(ocr_task.si(str(doc_id)))
            
        pipeline_tasks.append(metadata_enrichment_task.si(str(doc_id)))
        pipeline_tasks.append(bge_embed_task.si(str(doc_id)))

        if pipeline_tasks:
            chain(*pipeline_tasks).apply_async()
            logger.info(f"Re-scheduled adaptive ingestion pipeline for document {doc_id}.")
        else:
            logger.warning(f"No pipeline tasks selected for document {doc_id}.")

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

    if not check_document_permission(db, str(doc_id), current_context, "read"):
        raise HTTPException(status_code=403, detail="Access denied: read permission required.")

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

    if not check_document_permission(db, str(doc_id), current_context, "write"):
        raise HTTPException(status_code=403, detail="Access denied: write permission required.")

    # Check lock (enterprise only -- gate behind ENABLE_VERSIONING)
    from backend.app.core.config import features as _feat_del
    if _feat_del.ENABLE_VERSIONING:
        from datetime import datetime, timezone
        lock = db.query(DocumentLock).filter(DocumentLock.document_id == doc_id).first()
        if lock and lock.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            if lock.locked_by != uuid.UUID(current_context.user.id):
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Document is currently locked by another user."
                )

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
        parallel_tasks = [
            docling_parse_task.si(str(doc_id)),
            ocr_task.si(str(doc_id)),
            metadata_enrichment_task.si(str(doc_id))
        ]
        chord(group(*parallel_tasks), bge_embed_task.si(str(doc_id))).apply_async()
    else:
        document_repo.update_status(db, doc_id=doc_id, status="queued")
        
        try:
            from backend.app.services.document_analyzer import DocumentAnalyzer
            from backend.app.core.config import settings

            s3_obj = s3_storage.client.get_object(Bucket=s3_storage.bucket_name, Key=db_doc.storage_path)
            file_bytes = s3_obj['Body'].read()

            analyzer = DocumentAnalyzer(file_bytes=file_bytes, file_name=db_doc.name, file_type=db_doc.file_type)
            decision = analyzer.analyze()

            pipeline_tasks = []

            if settings.ENABLE_CLAMAV:
                pipeline_tasks.append(scan_malware_task.s(str(doc_id), db_doc.storage_path))
                first_vision_task = convert_to_pdf_task.s(str(doc_id))
            else:
                first_vision_task = convert_to_pdf_task.s({"status": "clean", "s3_key": db_doc.storage_path}, str(doc_id))

            if decision.run_vision and settings.ENABLE_VISION:
                pipeline_tasks.append(first_vision_task)
                pipeline_tasks.append(render_pages_task.s(str(doc_id)))
                pipeline_tasks.append(embed_and_index_task.s(str(doc_id)))

            if decision.run_docling and settings.DOCLING_ENABLED:
                pipeline_tasks.append(docling_parse_task.si(str(doc_id)))
                
            if decision.run_ocr and settings.ENABLE_OCR:
                pipeline_tasks.append(ocr_task.si(str(doc_id)))
                
            pipeline_tasks.append(metadata_enrichment_task.si(str(doc_id)))
            pipeline_tasks.append(bge_embed_task.si(str(doc_id)))

            if pipeline_tasks:
                chain(*pipeline_tasks).apply_async()
        except Exception as exc:
            logger.error(f"Failed to manually reprocess ingestion pipeline: {exc}")

    return {"status": "reprocessing_started", "pipeline": pipeline}

# ---------------------------------------------------------------------------
# Sprint 5: Discovery Endpoints (Recent, Frequent, Related)
# ---------------------------------------------------------------------------

@router.get("/recent", response_model=List[DocumentResponse])
def get_recent_documents(
    limit: int = 10,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/recent
    Retrieves the most recently viewed documents for the current user.
    """
    interactions = db.query(UserDocumentInteraction).filter(
        UserDocumentInteraction.user_id == current_context.user.id,
        UserDocumentInteraction.org_id == uuid.UUID(current_context.org_id)
    ).order_by(UserDocumentInteraction.last_interaction_at.desc()).limit(limit).all()
    
    doc_ids = [i.document_id for i in interactions]
    if not doc_ids:
        return []
        
    # Fetch documents and maintain order
    docs = db.query(document_repo.model).filter(document_repo.model.id.in_(doc_ids)).all()
    doc_map = {d.id: d for d in docs}
    return [doc_map[did] for did in doc_ids if did in doc_map]

@router.get("/frequent", response_model=List[DocumentResponse])
def get_frequent_documents(
    limit: int = 10,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/frequent
    Retrieves the most frequently viewed documents for the current user.
    """
    interactions = db.query(UserDocumentInteraction).filter(
        UserDocumentInteraction.user_id == current_context.user.id,
        UserDocumentInteraction.org_id == uuid.UUID(current_context.org_id)
    ).order_by(UserDocumentInteraction.count.desc()).limit(limit).all()
    
    doc_ids = [i.document_id for i in interactions]
    if not doc_ids:
        return []
        
    docs = db.query(document_repo.model).filter(document_repo.model.id.in_(doc_ids)).all()
    doc_map = {d.id: d for d in docs}
    return [doc_map[did] for did in doc_ids if did in doc_map]

class RelatedDocumentResponse(BaseModel):
    document: DocumentResponse
    relationship_type: str
    weight: float
    
    class Config:
        from_attributes = True

@router.get("/{doc_id}/related", response_model=List[RelatedDocumentResponse])
def get_related_documents(
    doc_id: uuid.UUID,
    limit: int = 5,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/{doc_id}/related
    Retrieves documents related to this one via the Knowledge Graph.
    """
    # Verify access to source document
    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc or str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=404, detail="Document not found.")

    from backend.app.core.config import features as _feat_rel
    # Knowledge Graph is an enterprise feature; return empty in Personal mode
    if not _feat_rel.ENABLE_KNOWLEDGE_GRAPH:
        return []

    edges = db.query(KnowledgeGraphEdge).filter(
        KnowledgeGraphEdge.source_document_id == doc_id
    ).order_by(KnowledgeGraphEdge.weight.desc()).limit(limit).all()
    
    response = []
    for edge in edges:
        target_doc = document_repo.get(db, id=edge.target_document_id)
        if target_doc:
            response.append({
                "document": target_doc,
                "relationship_type": edge.relationship_type,
                "weight": edge.weight
            })
            
    return response


# ---------------------------------------------------------------------------
# Sprint 11: Downloads and Versions
# ---------------------------------------------------------------------------

class SignedURLResponse(BaseModel):
    url: str
    expires_at: datetime


@router.get("/{doc_id}/download", response_model=SignedURLResponse)
def download_document(
    doc_id: uuid.UUID,
    current_context: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/{doc_id}/download
    Generates a signed URL for secure download. Applies dynamic watermark if configured.
    """
    if not check_document_permission(db, str(doc_id), current_context, "download"):
        raise HTTPException(status_code=403, detail="Access denied: download permission required.")

    doc = document_repo.get(db, id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    s3_key = doc.storage_path
    wm_config = get_document_watermark_config(db, doc_id, doc.folder_id)

    # If watermarking is needed and it's a PDF
    if wm_config and doc.file_type.lower() == "pdf":
        try:
            # Download original
            obj = s3_storage.client.get_object(Bucket=s3_storage.bucket_name, Key=s3_key)
            original_bytes = obj['Body'].read()

            # Apply watermark
            username = current_context.user.email if wm_config.include_username else None
            watermarked_bytes = apply_watermark_to_pdf(
                original_bytes,
                watermark_text=wm_config.watermark_text,
                username=username,
                include_timestamp=wm_config.include_timestamp,
                opacity=wm_config.opacity
            )

            # Upload to temp key
            temp_s3_key = f"temp/{doc_id}/watermarked_{current_context.user.id}.pdf"
            upload_bytes_with_sse(watermarked_bytes, temp_s3_key, content_type="application/pdf")
            s3_key = temp_s3_key
        except Exception as e:
            logger.error("Failed to apply watermark: %s", e)
            # Proceed with original file if watermark fails

    expires_sec = 900
    signed_url = generate_signed_download_url(
        document_id=str(doc_id),
        s3_key=s3_key,
        user_id=str(current_context.user.id),
        expires_seconds=expires_sec
    )

    import time
    return SignedURLResponse(
        url=signed_url,
        expires_at=datetime.fromtimestamp(time.time() + expires_sec)
    )


class DocumentVersionResponse(BaseModel):
    id: uuid.UUID
    version_number: int
    file_size: int
    change_note: Optional[str]
    created_at: datetime
    uploader_id: Optional[uuid.UUID]

    class Config:
        from_attributes = True


@router.get("/{doc_id}/versions", response_model=List[DocumentVersionResponse])
def list_versions(
    doc_id: uuid.UUID,
    current_context: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/{doc_id}/versions
    Lists all versions of a document.
    """
    if not check_document_permission(db, str(doc_id), current_context, "version"):
        raise HTTPException(status_code=403, detail="Access denied: version permission required.")

    versions = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc_id
    ).order_by(DocumentVersion.version_number.desc()).all()

    return versions


@router.post("/{doc_id}/versions", response_model=DocumentVersionResponse)
def upload_new_version(
    doc_id: uuid.UUID,
    change_note: str = Form(...),
    file: UploadFile = File(...),
    current_context: CurrentUserContext = Depends(get_current_user_context),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/documents/{doc_id}/versions
    Uploads a new version of the document.
    """
    if not check_document_permission(db, str(doc_id), current_context, "write"):
        raise HTTPException(status_code=403, detail="Access denied: write permission required.")
        
    doc = document_repo.get(db, id=doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check lock
    from datetime import datetime, timezone
    lock = db.query(DocumentLock).filter(DocumentLock.document_id == doc_id).first()
    if lock and lock.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
        if lock.locked_by != uuid.UUID(current_context.user.id):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Document is currently locked by another user."
            )

    file_bytes = file.file.read()
    file_size = len(file_bytes)
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    file.file.seek(0)

    # Get latest version number
    latest_ver = db.query(DocumentVersion).filter(
        DocumentVersion.document_id == doc_id
    ).order_by(DocumentVersion.version_number.desc()).first()
    
    next_ver_num = (latest_ver.version_number + 1) if latest_ver else 1

    s3_key = f"{doc.org_id}/{doc.id}/v{next_ver_num}_{file.filename}"
    
    # Upload with SSE
    from backend.app.services.security_service import get_sse_s3_headers
    s3_storage.client.upload_fileobj(
        file.file, 
        s3_storage.bucket_name, 
        s3_key,
        ExtraArgs=get_sse_s3_headers()
    )

    # Create new version record
    new_version = DocumentVersion(
        document_id=doc.id,
        org_id=doc.org_id,
        version_number=next_ver_num,
        s3_key=s3_key,
        file_size=file_size,
        file_hash=file_hash,
        uploader_id=uuid.UUID(current_context.user.id),
        change_note=change_note
    )
    db.add(new_version)
    
    # Update main doc storage_path to latest
    doc.storage_path = s3_key
    doc.file_size = file_size
    doc.file_hash = file_hash
    db.commit()
    db.refresh(new_version)

    return new_version


# ---------------------------------------------------------------------------
# Sprint 12: AI Intelligence Endpoints
# ---------------------------------------------------------------------------
import json
from typing import Dict, Any

class TimelineEvent(BaseModel):
    timestamp: datetime
    event_type: str
    description: str
    metadata: Optional[Dict[str, Any]] = None

@router.get("/{doc_id}/timeline", response_model=List[TimelineEvent])
def get_document_timeline(
    doc_id: uuid.UUID,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/{doc_id}/timeline
    Returns a chronological timeline of document events (creation, versions, processing, interactions).
    """
    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc or str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=404, detail="Document not found.")

    events = []
    
    # 1. Creation event
    events.append({
        "timestamp": db_doc.created_at,
        "event_type": "created",
        "description": "Document uploaded to system",
        "metadata": {"file_name": db_doc.name, "file_size": db_doc.file_size}
    })

    # 2. Versions
    versions = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc_id).all()
    for v in versions:
        events.append({
            "timestamp": v.created_at,
            "event_type": "version_upload",
            "description": f"Version {v.version_number} uploaded",
            "metadata": {"change_note": v.change_note}
        })

    # 3. Processing Jobs
    jobs = db.query(ProcessingJob).filter(ProcessingJob.document_id == doc_id, ProcessingJob.status == "completed").all()
    for job in jobs:
        events.append({
            "timestamp": job.completed_at or job.created_at,
            "event_type": "processing_completed",
            "description": f"Pipeline stage '{job.job_type}' completed",
            "metadata": {"metrics": json.loads(job.metrics_json) if job.metrics_json else None}
        })

    # Sort descending
    events.sort(key=lambda x: x["timestamp"], reverse=True)
    return events


@router.get("/topics/cluster", response_model=Dict[str, int])
def get_topic_clusters(
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/topics/cluster
    Aggregates all document topics for the organization into a frequency map.
    """
    summaries = db.query(DocumentSummary).filter(DocumentSummary.org_id == uuid.UUID(current_context.org_id)).all()
    topic_counts = {}
    for s in summaries:
        if s.topics_json:
            try:
                topics = json.loads(s.topics_json)
                for t in topics:
                    topic_counts[t] = topic_counts.get(t, 0) + 1
            except Exception:
                pass
    
    # Sort by frequency descending
    sorted_topics = dict(sorted(topic_counts.items(), key=lambda item: item[1], reverse=True))
    return sorted_topics


class DuplicateCandidate(BaseModel):
    document: DocumentResponse
    similarity_score: float
    
@router.get("/{doc_id}/duplicates", response_model=List[DuplicateCandidate])
def get_semantic_duplicates(
    doc_id: uuid.UUID,
    limit: int = 5,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/{doc_id}/duplicates
    Finds semantic duplicates using vector similarity on the document summary.
    """
    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc or str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=404, detail="Document not found.")

    summary = db.query(DocumentSummary).filter(DocumentSummary.document_id == doc_id).first()
    if not summary or not summary.summary:
        return []

    from backend.app.services.bge_service import get_bge_service
    from backend.app.core.qdrant import search_text_chunks
    
    bge = get_bge_service()
    query_vec = bge.encode_query(summary.summary[:1000])
    
    chunks = search_text_chunks(
        query_vector=query_vec,
        org_id=str(db_doc.org_id),
        team_ids=[],
        limit=20
    )
    
    # Aggregate scores by document ID
    doc_scores = {}
    for chunk in chunks:
        t_id = chunk.payload.get("document_id")
        if t_id and t_id != str(doc_id):
            if t_id not in doc_scores or chunk.score > doc_scores[t_id]:
                doc_scores[t_id] = chunk.score
                
    # Filter for high similarity (> 0.88 implies strong semantic overlap)
    candidates = []
    for t_id, score in doc_scores.items():
        if score > 0.88:
            target_doc = document_repo.get(db, id=uuid.UUID(t_id))
            if target_doc:
                candidates.append({
                    "document": target_doc,
                    "similarity_score": score
                })
                
    candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
    return candidates[:limit]


# ---------------------------------------------------------------------------
# Sprint 12: AI Intelligence Endpoints
# ---------------------------------------------------------------------------
import json
from typing import Dict, Any

class TimelineEvent(BaseModel):
    timestamp: datetime
    event_type: str
    description: str
    metadata: Optional[Dict[str, Any]] = None

@router.get("/{doc_id}/timeline", response_model=List[TimelineEvent])
def get_document_timeline(
    doc_id: uuid.UUID,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/{doc_id}/timeline
    Returns a chronological timeline of document events (creation, versions, processing, interactions).
    """
    """
    GET /api/v1/documents/{doc_id}/related
    Retrieves documents related to this one via the Knowledge Graph.
    """
    from backend.app.core.config import features as _feat_rel
    # Knowledge Graph is an enterprise feature; return empty in Personal mode
    if not _feat_rel.ENABLE_KNOWLEDGE_GRAPH:
        return []

    # Verify access to source document
    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc or str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=404, detail="Document not found.")

    edges = db.query(KnowledgeGraphEdge).filter(
        KnowledgeGraphEdge.source_document_id == doc_id
    ).order_by(KnowledgeGraphEdge.weight.desc()).limit(limit).all()
    
    response = []
    for edge in edges:
        target_doc = document_repo.get(db, id=edge.target_document_id)
        if target_doc:
            response.append({
                "document": target_doc,
                "relationship_type": edge.relationship_type,
                "weight": edge.weight
            })
            
    return response

    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc or str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=404, detail="Document not found.")

    events = []
    
    # 1. Creation event
    events.append({
        "timestamp": db_doc.created_at,
        "event_type": "created",
        "description": "Document uploaded to system",
        "metadata": {"file_name": db_doc.name, "file_size": db_doc.file_size}
    })

    # 2. Versions
    versions = db.query(DocumentVersion).filter(DocumentVersion.document_id == doc_id).all()
    for v in versions:
        events.append({
            "timestamp": v.created_at,
            "event_type": "version_upload",
            "description": f"Version {v.version_number} uploaded",
            "metadata": {"change_note": v.change_note}
        })

    # 3. Processing Jobs
    jobs = db.query(ProcessingJob).filter(ProcessingJob.document_id == doc_id, ProcessingJob.status == "completed").all()
    for job in jobs:
        events.append({
            "timestamp": job.completed_at or job.created_at,
            "event_type": "processing_completed",
            "description": f"Pipeline stage '{job.job_type}' completed",
            "metadata": {"metrics": json.loads(job.metrics_json) if job.metrics_json else None}
        })

    # Sort descending
    events.sort(key=lambda x: x["timestamp"], reverse=True)
    return events


@router.get("/topics/cluster", response_model=Dict[str, int])
def get_topic_clusters(
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/topics/cluster
    Aggregates all document topics for the organization into a frequency map.
    """
    summaries = db.query(DocumentSummary).filter(DocumentSummary.org_id == uuid.UUID(current_context.org_id)).all()
    topic_counts = {}
    for s in summaries:
        if s.topics_json:
            try:
                topics = json.loads(s.topics_json)
                for t in topics:
                    topic_counts[t] = topic_counts.get(t, 0) + 1
            except Exception:
                pass
    
    # Sort by frequency descending
    sorted_topics = dict(sorted(topic_counts.items(), key=lambda item: item[1], reverse=True))
    return sorted_topics


class DuplicateCandidate(BaseModel):
    document: DocumentResponse
    similarity_score: float
    
@router.get("/{doc_id}/duplicates", response_model=List[DuplicateCandidate])
def get_semantic_duplicates(
    doc_id: uuid.UUID,
    limit: int = 5,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:read")),
    db: Session = Depends(get_db)
):
    """
    GET /api/v1/documents/{doc_id}/duplicates
    Finds semantic duplicates using vector similarity on the document summary.
    """
    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc or str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=404, detail="Document not found.")

    summary = db.query(DocumentSummary).filter(DocumentSummary.document_id == doc_id).first()
    if not summary or not summary.summary:
        return []

    from backend.app.services.bge_service import get_bge_service
    from backend.app.core.qdrant import search_text_chunks
    
    bge = get_bge_service()
    query_vec = bge.encode_query(summary.summary[:1000])
    
    chunks = search_text_chunks(
        query_vector=query_vec,
        org_id=str(db_doc.org_id),
        team_ids=[],
        limit=20
    )
    
    # Aggregate scores by document ID
    doc_scores = {}
    for chunk in chunks:
        t_id = chunk.payload.get("document_id")
        if t_id and t_id != str(doc_id):
            if t_id not in doc_scores or chunk.score > doc_scores[t_id]:
                doc_scores[t_id] = chunk.score
                
    # Filter for high similarity (> 0.88 implies strong semantic overlap)
    candidates = []
    for t_id, score in doc_scores.items():
        if score > 0.88:
            target_doc = document_repo.get(db, id=uuid.UUID(t_id))
            if target_doc:
                candidates.append({
                    "document": target_doc,
                    "similarity_score": score
                })
                
    candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
    return candidates[:limit]

@router.post("/{doc_id}/archive", response_model=DocumentResponse)
def archive_document(
    doc_id: uuid.UUID,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:write")),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/documents/{doc_id}/archive
    Archives a document.
    """
    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc or str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=404, detail="Document not found.")

    db_doc.is_archived = True
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    return db_doc

@router.post("/{doc_id}/restore", response_model=DocumentResponse)
def restore_document(
    doc_id: uuid.UUID,
    current_context: CurrentUserContext = Depends(PermissionChecker("documents:write")),
    db: Session = Depends(get_db)
):
    """
    POST /api/v1/documents/{doc_id}/restore
    Restores an archived document.
    """
    db_doc = document_repo.get(db, id=doc_id)
    if not db_doc or str(db_doc.org_id) != current_context.org_id:
        raise HTTPException(status_code=404, detail="Document not found.")

    db_doc.is_archived = False
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    return db_doc

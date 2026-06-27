import pytest
import uuid
from unittest.mock import patch, MagicMock
from backend.app.models.models import Organization, Folder, Document, DocumentPage
from backend.app.repositories.base_repo import document_repo, document_page_repo
from backend.app.tasks.tasks import scan_malware_task, convert_to_pdf_task, render_pages_task, embed_and_index_task


@patch("backend.app.tasks.tasks.s3_storage")
@patch("backend.app.tasks.tasks.clamd")
@patch("backend.app.tasks.tasks.subprocess")
@patch("backend.app.tasks.tasks.shutil")
@patch("backend.app.tasks.tasks.convert_from_path")
@patch("backend.app.tasks.tasks.qdrant_client")
@patch("backend.app.tasks.tasks.SessionLocal")
def test_full_ingestion_pipeline_e2e(
    mock_session,
    mock_qdrant_client,
    mock_convert_from_path,
    mock_shutil,
    mock_subprocess,
    mock_clamd,
    mock_s3_storage,
    db
):
    """
    Day 10: Ingestion Flow Integration Test.
    Performs end-to-end integration test verifying that the Celery pipeline runs,
    correctly transitions PostgreSQL status from queued -> processing -> completed,
    creates document page records, and upserts payloads to Qdrant.
    """
    # 1. Setup mock database session
    db.close = MagicMock()  # Prevent tasks from closing test session
    mock_session.return_value = db

    # 2. Setup mock organization, folder, and document in DB
    org = Organization(name="Test Org")
    db.add(org)
    db.commit()
    db.refresh(org)

    team_uuid = uuid.uuid4()
    folder = Folder(name="Test Folder", org_id=org.id, team_id=team_uuid)
    db.add(folder)
    db.commit()
    db.refresh(folder)

    # Register document as 'queued'
    doc_in = {
        "org_id": org.id,
        "folder_id": folder.id,
        "name": "document.docx",
        "storage_path": f"{org.id}/document.docx",
        "status": "queued",
        "file_type": "docx",
        "file_size": 2048
    }
    doc = document_repo.create(db, obj_in=doc_in)

    # 3. Setup mock external service responses
    # Mock S3 file retrieval and uploads
    mock_body = MagicMock()
    mock_body.read.return_value = b"mock file bytes"
    mock_s3_storage.client.get_object.return_value = {"Body": mock_body}
    mock_s3_storage.bucket_name = "test-bucket"

    # Mock ClamAV (Clean result)
    mock_cd = MagicMock()
    mock_cd.scan_stream.return_value = {"stream": ("OK", None)}
    mock_clamd.ClamdNetworkSocket.return_value = mock_cd

    # Mock LibreOffice (shutil finds it, subprocess runs cleanly)
    mock_shutil.which.return_value = "/usr/bin/libreoffice"
    mock_subprocess.run.return_value = MagicMock(returncode=0)

    # Mock pdf2image (Renders 2 pages)
    page1 = MagicMock()
    page2 = MagicMock()
    mock_convert_from_path.return_value = [page1, page2]

    # Mock Qdrant client upsert
    mock_qdrant_client.upsert.return_value = MagicMock()

    # 4. RUN PIPELINE TASKS SEQUENTIALLY (representing Celery signature chain)
    # Step A: Malware scan
    result_scan = scan_malware_task(str(doc.id), doc.storage_path)
    assert result_scan["status"] == "clean"
    
    # Verify status transitioned to 'processing'
    db.refresh(doc)
    assert doc.status == "processing"

    # Step B: Conversion
    result_conv = convert_to_pdf_task(result_scan, str(doc.id))
    assert result_conv["status"] == "converted"
    assert result_conv["pdf_s3_key"] == f"{org.id}/document.pdf"

    # Step C: Page rendering
    result_render = render_pages_task(result_conv, str(doc.id))
    assert result_render["status"] == "rendered"
    assert len(result_render["rendered_pages"]) == 2

    # Verify document page records were created in database
    db_pages = document_page_repo.get_by_document(db, doc.id)
    assert len(db_pages) == 2
    assert db_pages[0].page_number == 1
    assert db_pages[1].page_number == 2

    # Step D: Vector Embedding & Ingestion
    result_embed = embed_and_index_task(result_render, str(doc.id))
    assert result_embed["status"] == "completed"

    # 5. VERIFY FINAL DATABASE & VEC STORE STATE
    db.refresh(doc)
    # Check overall status updated to 'completed'
    assert doc.status == "completed"

    # Check database matching Qdrant point IDs
    db_pages = document_page_repo.get_by_document(db, doc.id)
    assert db_pages[0].qdrant_point_id is not None
    assert db_pages[1].qdrant_point_id is not None

    # Check Qdrant upsert was called with the exact payload and metadata
    assert mock_qdrant_client.upsert.call_count == 2
    
    # Retrieve payload from mock call args
    call_args = mock_qdrant_client.upsert.call_args_list[0]
    upserted_point = call_args.kwargs["points"][0]
    
    assert upserted_point.payload["org_id"] == str(org.id)
    assert upserted_point.payload["folder_id"] == str(folder.id)
    assert upserted_point.payload["document_id"] == str(doc.id)
    assert upserted_point.payload["allowed_teams"] == [str(team_uuid)]

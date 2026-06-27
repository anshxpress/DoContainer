import pytest
import uuid
from unittest.mock import patch, MagicMock
from backend.app.tasks.tasks import scan_malware_task, convert_to_pdf_task, render_pages_task, embed_and_index_task

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_document():
    doc = MagicMock()
    doc.id = "test-doc-id"
    doc.org_id = "test-org-id"
    doc.file_type = "docx"
    return doc

@patch("backend.app.tasks.tasks.SessionLocal")
@patch("backend.app.tasks.tasks.document_repo")
@patch("backend.app.tasks.tasks.s3_storage")
@patch("backend.app.tasks.tasks.clamd")
def test_scan_malware_task_clean(mock_clamd, mock_s3_storage, mock_doc_repo, mock_session, mock_db):
    mock_session.return_value = mock_db
    
    # Mock S3 object read
    mock_body = MagicMock()
    mock_body.read.return_value = b"clean file content"
    mock_s3_storage.client.get_object.return_value = {"Body": mock_body}
    mock_s3_storage.bucket_name = "test-bucket"

    # Mock ClamAV response (Clean)
    mock_cd = MagicMock()
    mock_cd.scan_stream.return_value = {"stream": ("OK", None)}
    mock_clamd.ClamdNetworkSocket.return_value = mock_cd

    result = scan_malware_task("test-doc-id", "test-org-id/test-doc-id/1/file.docx")
    
    assert result["status"] == "clean"
    assert result["s3_key"] == "test-org-id/test-doc-id/1/file.docx"
    
    # Assert database updates
    mock_doc_repo.update_status.assert_any_call(mock_db, doc_id="test-doc-id", status="processing")


@patch("backend.app.tasks.tasks.SessionLocal")
@patch("backend.app.tasks.tasks.document_repo")
@patch("backend.app.tasks.tasks.s3_storage")
@patch("backend.app.tasks.tasks.clamd")
def test_scan_malware_task_infected(mock_clamd, mock_s3_storage, mock_doc_repo, mock_session, mock_db):
    mock_session.return_value = mock_db
    
    # Mock S3 object read
    mock_body = MagicMock()
    mock_body.read.return_value = b"infected file content"
    mock_s3_storage.client.get_object.return_value = {"Body": mock_body}
    mock_s3_storage.bucket_name = "test-bucket"

    # Mock ClamAV response (Infected)
    mock_cd = MagicMock()
    mock_cd.scan_stream.return_value = {"stream": ("FOUND", "Eicar-Test-Signature")}
    mock_clamd.ClamdNetworkSocket.return_value = mock_cd

    result = scan_malware_task("test-doc-id", "test-org-id/test-doc-id/1/file.docx")
    
    assert result["status"] == "infected"
    assert result["virus"] == "Eicar-Test-Signature"
    
    # Assert database updates to failed
    mock_doc_repo.update_status.assert_any_call(mock_db, doc_id="test-doc-id", status="failed", error_message="Malware detected: Eicar-Test-Signature")
    # Assert quarantine copy & delete
    mock_s3_storage.client.copy_object.assert_called_once()
    mock_s3_storage.client.delete_object.assert_called_once()


@patch("backend.app.tasks.tasks.SessionLocal")
@patch("backend.app.tasks.tasks.document_repo")
@patch("backend.app.tasks.tasks.s3_storage")
@patch("backend.app.tasks.tasks.subprocess")
@patch("backend.app.tasks.tasks.shutil")
def test_convert_to_pdf_task_docx(mock_shutil, mock_subprocess, mock_s3_storage, mock_doc_repo, mock_session, mock_db, mock_document):
    mock_session.return_value = mock_db
    mock_doc_repo.get.return_value = mock_document
    mock_s3_storage.bucket_name = "test-bucket"
    mock_shutil.which.return_value = "/usr/bin/libreoffice"

    prev_result = {"status": "clean", "s3_key": "test-org-id/test-doc-id/1/file.docx"}
    result = convert_to_pdf_task(prev_result, "test-doc-id")
    
    assert result["status"] == "converted"
    assert result["pdf_s3_key"] == "test-org-id/test-doc-id/1/file.pdf"
    
    # Assert LibreOffice subprocess was run
    mock_subprocess.run.assert_called_once()
    # Assert converted PDF uploaded
    mock_s3_storage.upload_file.assert_called_once()


@patch("backend.app.tasks.tasks.SessionLocal")
@patch("backend.app.tasks.tasks.document_repo")
@patch("backend.app.tasks.tasks.document_page_repo")
@patch("backend.app.tasks.tasks.s3_storage")
@patch("backend.app.tasks.tasks.convert_from_path")
def test_render_pages_task_pdf(mock_convert_from_path, mock_s3_storage, mock_page_repo, mock_doc_repo, mock_session, mock_db, mock_document):
    mock_session.return_value = mock_db
    mock_document.file_type = "pdf"
    mock_doc_repo.get.return_value = mock_document
    mock_s3_storage.bucket_name = "test-bucket"
    
    # Mock 2 PDF pages
    page1 = MagicMock()
    page2 = MagicMock()
    mock_convert_from_path.return_value = [page1, page2]

    # Mock DB Page creation return value
    mock_page = MagicMock()
    mock_page.id = uuid.uuid4()
    mock_page_repo.create.return_value = mock_page

    prev_result = {"status": "converted", "pdf_s3_key": "test-org-id/test-doc-id/1/file.pdf"}
    result = render_pages_task(prev_result, "test-doc-id")
    
    assert result["status"] == "rendered"
    assert len(result["rendered_pages"]) == 2
    assert result["rendered_pages"][0][0] == 1
    assert result["rendered_pages"][1][0] == 2
    
    # Assert png files uploaded to S3
    assert mock_s3_storage.upload_file.call_count == 2
    # Assert document page entries saved to DB
    assert mock_page_repo.create.call_count == 2


@patch("backend.app.tasks.tasks.SessionLocal")
@patch("backend.app.tasks.tasks.document_repo")
@patch("backend.app.tasks.tasks.document_page_repo")
@patch("backend.app.tasks.tasks.qdrant_client")
def test_embed_and_index_task(mock_qdrant_client, mock_page_repo, mock_doc_repo, mock_session, mock_db, mock_document):
    mock_session.return_value = mock_db
    mock_doc_repo.get.return_value = mock_document
    
    page_id_1 = str(uuid.uuid4())
    page_id_2 = str(uuid.uuid4())
    prev_result = {
        "status": "rendered",
        "rendered_pages": [
            (1, page_id_1, "path/to/page_1.png"),
            (2, page_id_2, "path/to/page_2.png")
        ]
    }
    
    mock_page_record_1 = MagicMock()
    mock_page_record_2 = MagicMock()
    mock_page_repo.get.side_effect = [mock_page_record_1, mock_page_record_2]

    result = embed_and_index_task(prev_result, "test-doc-id")
    
    assert result["status"] == "completed"
    assert len(result["indexed_points"]) == 2
    assert mock_qdrant_client.upsert.call_count == 2
    
    # Assert PG status updated to completed
    mock_doc_repo.update_status.assert_called_once_with(mock_db, doc_id="test-doc-id", status="completed")
    
    # Assert qdrant point IDs were written back to DB
    assert mock_page_record_1.qdrant_point_id is not None
    assert mock_page_record_2.qdrant_point_id is not None


from backend.app.tasks.partition_tasks import create_monthly_partitions_task

@patch("backend.app.tasks.partition_tasks.SessionLocal")
def test_create_monthly_partitions_task(mock_session):
    mock_db = MagicMock()
    mock_session.return_value = mock_db
    
    create_monthly_partitions_task()
    
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.close.assert_called_once()



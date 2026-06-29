import pytest
from unittest.mock import patch, MagicMock

@patch("backend.app.tasks.ocr_tasks.SessionLocal")
@patch("backend.app.tasks.ocr_tasks.document_repo")
@patch("backend.app.services.ocr_service.get_ocr_service")
def test_ocr_task_basic(mock_get_ocr, mock_doc_repo, mock_session_local):
    from backend.app.tasks.ocr_tasks import ocr_task
    from backend.app.models.models import DocumentPage
    
    mock_db = MagicMock()
    mock_session_local.return_value = mock_db
    
    mock_doc = MagicMock()
    mock_doc.org_id = "org-123"
    mock_doc_repo.get.return_value = mock_doc
    
    mock_ocr_instance = MagicMock()
    mock_ocr_instance.is_scanned_page.return_value = True
    
    mock_chunk = MagicMock()
    mock_chunk.text = "Sample"
    mock_chunk.confidence = 0.99
    mock_chunk.language = "en"
    mock_chunk.bbox_x0 = 0.0
    mock_chunk.bbox_y0 = 0.0
    mock_chunk.bbox_x1 = 1.0
    mock_chunk.bbox_y1 = 1.0
    mock_chunk.reading_order = 1
    
    mock_ocr_instance.run_page_ocr.return_value = [mock_chunk]
    mock_get_ocr.return_value = mock_ocr_instance
    
    # We just want to ensure it doesn't crash on mocked execution
    with patch("backend.app.core.s3.s3_storage.client.download_file") as mock_download:
        with patch("backend.app.repositories.base_repo.document_page_repo.get_by_document") as mock_get_pages:
            mock_page = MagicMock()
            mock_page.page_number = 1
            mock_page.text_content = ""
            mock_page.png_storage_path = "path/to.png"
            mock_get_pages.return_value = [mock_page]
            
            ocr_task("00000000-0000-0000-0000-000000000123")
    
    assert mock_ocr_instance.run_page_ocr.called
    assert mock_db.add.called
    assert mock_db.commit.called

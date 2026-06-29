import pytest
from unittest.mock import patch, MagicMock
import asyncio

@pytest.fixture
def mock_call_gemini():
    with patch("backend.app.services.metadata_service._call_gemini") as mock_call:
        mock_call.return_value = '{"summary": "Test Summary", "complexity_score": 0.8}'
        yield mock_call

def test_metadata_service_enrich(mock_call_gemini):
    from backend.app.services.metadata_service import enrich_document_metadata
    
    mock_db = MagicMock()
    mock_doc_query = MagicMock()
    mock_doc = MagicMock()
    mock_doc.id = "doc-123"
    mock_doc_query.filter.return_value.first.return_value = mock_doc
    mock_db.query.return_value = mock_doc_query
    
    full_text = "This is a long document text for testing purposes."
    
    # Run async function
    loop = asyncio.get_event_loop()
    loop.run_until_complete(enrich_document_metadata(mock_db, "00000000-0000-0000-0000-000000000123", full_text, "00000000-0000-0000-0000-000000000456"))
    
    assert mock_db.add.called
    assert mock_db.commit.called

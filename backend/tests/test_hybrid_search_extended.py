import pytest
from unittest.mock import patch, MagicMock

def test_hybrid_search_mode_parsing():
    from backend.app.schemas.schemas import SearchMode
    assert SearchMode.HYBRID.value == "hybrid"
    assert SearchMode.VISION.value == "vision"
    assert SearchMode.TEXT.value == "text"
    assert SearchMode.KEYWORD.value == "keyword"

@patch("backend.app.services.search_service.search_pages")
@patch("backend.app.services.search_service.search_text_chunks")
@patch("backend.app.services.search_service.get_bge_service")
def test_hybrid_search_text_only(mock_bge, mock_text_search, mock_vision_search):
    from backend.app.services.search_service import hybrid_search
    from backend.app.schemas.schemas import SearchMode
    
    mock_bge_instance = MagicMock()
    mock_bge_instance.encode_query.return_value = [0.1]*1024
    mock_bge.return_value = mock_bge_instance
    
    mock_text_search.return_value = []
    
    mock_db = MagicMock()
    results = hybrid_search(mock_db, "test", "org-1", team_ids=[], search_mode=SearchMode.TEXT, top_k=5)
    
    assert mock_vision_search.called is False
    assert mock_text_search.called is True

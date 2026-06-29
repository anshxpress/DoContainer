import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_flag_model():
    with patch("backend.app.services.bge_service.BGEM3Service._get_model") as mock_model:
        mock_instance = MagicMock()
        # Mock numpy array tolist()
        mock_numpy_arr = MagicMock()
        mock_numpy_arr.tolist.return_value = [0.1] * 1024
        mock_instance.encode.return_value = {"dense_vecs": [mock_numpy_arr]}
        mock_model.return_value = mock_instance
        yield mock_model

@pytest.fixture
def mock_flag_reranker():
    with patch("backend.app.services.bge_service.BGERerankerService._get_reranker") as mock_reranker:
        mock_instance = MagicMock()
        mock_instance.compute_score.return_value = [0.8, 0.2]
        mock_reranker.return_value = mock_instance
        yield mock_reranker

def test_bge_m3_service(mock_flag_model):
    from backend.app.services.bge_service import BGEM3Service
    service = BGEM3Service()
    
    embeddings = service.encode_texts(["Hello world"])
    assert len(embeddings) == 1
    assert len(embeddings[0]) == 1024

def test_bge_reranker_service(mock_flag_reranker):
    from backend.app.services.bge_service import BGERerankerService
    service = BGERerankerService()
    
    query = "test query"
    docs = ["doc 1", "doc 2"]
    scores = service.rerank(query, docs)
    
    assert len(scores) == 2
    assert scores == [0.8, 0.2]

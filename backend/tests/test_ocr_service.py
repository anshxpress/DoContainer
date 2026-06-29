import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_ocr_engine():
    with patch("backend.app.services.ocr_service.PaddleOCRService._get_engine") as mock_get_engine:
        mock_instance = MagicMock()
        # Raw results shape: [[[[x0,y0],[x1,y1],[x2,y2],[x3,y3]], (text, confidence)], ...]
        mock_instance.ocr.return_value = [
            [
                [[[10, 10], [100, 10], [100, 50], [10, 50]], ("Test OCR Text", 0.95)]
            ]
        ]
        mock_get_engine.return_value = mock_instance
        yield mock_get_engine

def test_ocr_service_initialization():
    from backend.app.services.ocr_service import PaddleOCRService
    service = PaddleOCRService()
    assert service._engine is None

def test_ocr_service_extract(mock_ocr_engine, tmp_path):
    from backend.app.services.ocr_service import PaddleOCRService
    from PIL import Image
    
    img_path = tmp_path / "test.png"
    img = Image.new("RGB", (100, 100), color="white")
    img.save(img_path)

    service = PaddleOCRService()
    results = service.run_page_ocr(str(img_path))
    
    assert len(results) == 1
    assert results[0].text == "Test OCR Text"
    assert results[0].confidence == 0.95

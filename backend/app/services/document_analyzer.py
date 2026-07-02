import logging
import fitz  # PyMuPDF
from typing import Dict, Any, List
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class PipelineDecision(BaseModel):
    is_digital_pdf: bool = False
    is_scanned_pdf: bool = False
    is_image_heavy: bool = False
    
    # Execution flags
    run_ocr: bool = True
    run_vision: bool = True
    run_docling: bool = True
    
    # Metadata
    page_count: int = 0
    image_count: int = 0
    text_length: int = 0
    estimated_images_per_page: float = 0.0

class DocumentAnalyzer:
    """
    Analyzes document bytes to determine the optimal processing pipeline.
    """
    
    def __init__(self, file_bytes: bytes, file_name: str, file_type: str):
        self.file_bytes = file_bytes
        self.file_name = file_name.lower()
        self.file_type = file_type.lower()
        
    def analyze(self) -> PipelineDecision:
        decision = PipelineDecision()
        
        if self.file_type not in ["pdf"]:
            # If it's an image natively, it needs OCR and Vision usually
            if self.file_type in ["jpg", "jpeg", "png"]:
                decision.is_scanned_pdf = True
                decision.page_count = 1
                decision.image_count = 1
                return decision
            return decision

        try:
            doc = fitz.open(stream=self.file_bytes, filetype="pdf")
            decision.page_count = len(doc)
            
            total_text_length = 0
            pages_with_images = 0
            
            for page in doc:
                text = page.get_text("text")
                if text:
                    total_text_length += len(text.strip())
                
                images = page.get_images()
                if images:
                    decision.image_count += len(images)
                    pages_with_images += 1
                    
            decision.text_length = total_text_length
            if decision.page_count > 0:
                decision.estimated_images_per_page = decision.image_count / decision.page_count
                
            # Heuristic 1: Is it scanned?
            # If average text per page is very low, it's likely scanned.
            avg_text_per_page = total_text_length / decision.page_count if decision.page_count else 0
            if avg_text_per_page < 50:
                decision.is_scanned_pdf = True
                decision.run_ocr = True
            else:
                decision.is_digital_pdf = True
                decision.run_ocr = False
                
            # Heuristic 2: Is it image-heavy or requires vision?
            image_page_ratio = pages_with_images / decision.page_count if decision.page_count else 0
            
            # Simple keyword checks in filename for engineering/charts/medical/scientific
            keywords = ["chart", "map", "drawing", "medical", "diagram", "schematic"]
            filename_matches_vision = any(kw in self.file_name for kw in keywords)
            
            if image_page_ratio > 0.3 or filename_matches_vision:
                decision.is_image_heavy = True
                decision.run_vision = True
            else:
                decision.run_vision = False
                
            doc.close()
        except Exception as e:
            logger.error(f"Failed to analyze PDF with PyMuPDF: {e}")
            # Fallback to safest route: run everything
            decision.run_ocr = True
            decision.run_vision = True
            
        return decision

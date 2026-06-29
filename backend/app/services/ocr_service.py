"""
Hybrid Pipeline — PaddleOCR Service

Wraps PaddleOCR with lazy-loading, GPU auto-detection, scanned-page detection,
per-page OCR, language detection, and confidence filtering.

Designed for use inside Celery workers (the ocr-pipeline queue) where the
model is loaded once at worker startup via the module-level singleton.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class OcrResult:
    """A single recognised text region on a page."""
    text: str
    confidence: float
    language: str
    # Normalised bounding box (0.0–1.0 relative to page dimensions)
    bbox_x0: float
    bbox_y0: float
    bbox_x1: float
    bbox_y1: float
    reading_order: int = 0


# ---------------------------------------------------------------------------
# PaddleOCR Service
# ---------------------------------------------------------------------------

class PaddleOCRService:
    """
    Thin wrapper around PaddleOCR with:
    - Lazy model loading (first call triggers download if needed)
    - GPU auto-detection with CPU fallback
    - Scanned-page heuristic (text length threshold)
    - Language detection via langdetect
    - Confidence filtering
    """

    def __init__(self) -> None:
        self._engine = None  # lazy loaded

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_engine(self):
        """Lazily initialise PaddleOCR on first use."""
        if self._engine is not None:
            return self._engine

        os.environ.setdefault("PADDLE_HOME", settings.PADDLE_HOME)
        os.makedirs(settings.PADDLE_HOME, exist_ok=True)

        try:
            from paddleocr import PaddleOCR
            import paddle

            use_gpu = paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0
            logger.info(f"Initialising PaddleOCR engine (use_gpu={use_gpu})…")

            self._engine = PaddleOCR(
                use_angle_cls=True,
                lang="en",          # default; per-page detection handled by langdetect
                use_gpu=use_gpu,
                show_log=False,
            )
            logger.info("PaddleOCR engine initialised successfully.")
        except ImportError:
            logger.warning(
                "PaddleOCR is not installed. "
                "OCR tasks will return empty results. "
                "Install paddlepaddle + paddleocr to enable OCR."
            )
            self._engine = None

        return self._engine

    def _detect_language(self, text: str) -> str:
        """Detect ISO-639-1 language code for a text block."""
        if not text or len(text.strip()) < 5:
            return "en"
        try:
            from langdetect import detect
            return detect(text) or "en"
        except Exception:
            return "en"

    def _normalize_bbox(
        self,
        quad_points: List[List[float]],
        img_width: int,
        img_height: int,
    ) -> tuple[float, float, float, float]:
        """
        Convert PaddleOCR quadrilateral points [[x0,y0],[x1,y1],[x2,y2],[x3,y3]]
        to a normalised AABB (x0, y0, x1, y1) in 0.0–1.0 space.
        """
        xs = [p[0] for p in quad_points]
        ys = [p[1] for p in quad_points]
        x0 = max(0.0, min(xs) / img_width)
        y0 = max(0.0, min(ys) / img_height)
        x1 = min(1.0, max(xs) / img_width)
        y1 = min(1.0, max(ys) / img_height)
        return x0, y0, x1, y1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_scanned_page(self, text_content: Optional[str]) -> bool:
        """
        Return True when the embedded text content is too short to be useful,
        indicating a scanned / image-only page that needs OCR.
        """
        return len((text_content or "").strip()) < settings.OCR_SCANNED_TEXT_THRESHOLD

    def run_page_ocr(self, image_path: str) -> List[OcrResult]:
        """
        Run PaddleOCR on a single page image and return filtered OcrResult list.

        Results with confidence < OCR_CONFIDENCE_MIN are discarded.
        Language is detected once for the concatenated page text.
        """
        engine = self._get_engine()
        if engine is None:
            return []

        try:
            from PIL import Image as PILImage
            img = PILImage.open(image_path)
            img_width, img_height = img.size
        except Exception as exc:
            logger.error(f"Failed to open image '{image_path}': {exc}")
            return []

        try:
            raw_results = engine.ocr(image_path, cls=True)
        except Exception as exc:
            logger.error(f"PaddleOCR inference failed on '{image_path}': {exc}")
            return []

        # raw_results shape: [[[[x0,y0],[x1,y1],[x2,y2],[x3,y3]], (text, confidence)], ...]
        results: List[OcrResult] = []

        if not raw_results or not raw_results[0]:
            return results

        # Detect language from the full page text for efficiency
        full_page_text = " ".join(
            line[1][0] for line in raw_results[0] if line and line[1]
        )
        page_lang = self._detect_language(full_page_text)

        for order, line in enumerate(raw_results[0]):
            if not line or len(line) < 2:
                continue
            quad_points, (text, conf) = line[0], line[1]
            if conf < settings.OCR_CONFIDENCE_MIN:
                continue
            x0, y0, x1, y1 = self._normalize_bbox(quad_points, img_width, img_height)
            results.append(
                OcrResult(
                    text=text,
                    confidence=float(conf),
                    language=page_lang,
                    bbox_x0=x0,
                    bbox_y0=y0,
                    bbox_x1=x1,
                    bbox_y1=y1,
                    reading_order=order,
                )
            )

        return results

    def batch_ocr_pages(
        self,
        page_paths: List[str],
    ) -> Dict[int, List[OcrResult]]:
        """
        OCR a list of page image paths in sequence.

        Args:
            page_paths: Ordered list of absolute file paths to page PNGs.

        Returns:
            Dict mapping 1-based page_number → List[OcrResult].
        """
        return {
            page_num: self.run_page_ocr(path)
            for page_num, path in enumerate(page_paths, start=1)
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_ocr_service_instance: Optional[PaddleOCRService] = None


def get_ocr_service() -> PaddleOCRService:
    """Return the process-level PaddleOCRService singleton."""
    global _ocr_service_instance
    if _ocr_service_instance is None:
        _ocr_service_instance = PaddleOCRService()
    return _ocr_service_instance

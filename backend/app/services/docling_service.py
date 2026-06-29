"""
Hybrid Pipeline — Docling Document Parser Service

Wraps Docling's DocumentConverter for structure-aware parsing of PDFs and
Office documents. Extracts headings, paragraphs, tables, figures, captions,
lists, headers, and footers with normalised bounding boxes and reading order.

Per the implementation plan (Q1), Docling runs in parallel with the existing
PyMuPDF page renderer — it produces structured parse elements for text
embedding; PyMuPDF still produces the PNG images consumed by ColQwen2.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class ParseElement:
    """A single structured element extracted from a page."""
    element_type: str       # heading/paragraph/table/image/figure/list/caption/header/footer
    content: Optional[str]  # textual content (None for pure image elements)
    page_number: int
    reading_order: int
    # Normalised bounding box (0.0–1.0)
    bbox_x0: Optional[float] = None
    bbox_y0: Optional[float] = None
    bbox_x1: Optional[float] = None
    bbox_y1: Optional[float] = None


@dataclass
class DoclingResult:
    """Result of a single document parse operation."""
    elements: List[ParseElement] = field(default_factory=list)
    page_count: int = 0
    success: bool = True
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Docling Parser Service
# ---------------------------------------------------------------------------

class DoclingParserService:
    """
    Structure-aware document parser using Docling.

    Supports PDF and Office formats (docx, pptx, xlsx).
    Falls back to an empty DoclingResult when Docling is not installed or
    DOCLING_ENABLED is False.
    """

    # Mapping from Docling label strings → canonical element_type strings
    _TYPE_MAP: dict = {
        "title": "heading",
        "section_header": "heading",
        "page_header": "header",
        "page_footer": "footer",
        "text": "paragraph",
        "paragraph": "paragraph",
        "list_item": "list",
        "table": "table",
        "picture": "image",
        "figure": "figure",
        "caption": "caption",
        "formula": "paragraph",
        "footnote": "paragraph",
        "code": "paragraph",
    }

    def _detect_element_type(self, label: str) -> str:
        return self._TYPE_MAP.get(label.lower(), "paragraph")

    def _normalize_bbox(
        self,
        bbox,
        page_width: float,
        page_height: float,
    ) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        """Convert Docling BoundingBox → normalised 0.0–1.0 coords."""
        if bbox is None or page_width <= 0 or page_height <= 0:
            return None, None, None, None
        try:
            x0 = max(0.0, float(bbox.l) / page_width)
            y0 = max(0.0, float(bbox.t) / page_height)
            x1 = min(1.0, float(bbox.r) / page_width)
            y1 = min(1.0, float(bbox.b) / page_height)
            return x0, y0, x1, y1
        except Exception:
            return None, None, None, None

    def parse_document(self, file_path: str, file_type: str) -> DoclingResult:
        """
        Parse a document and return its structural elements.

        Args:
            file_path:  Absolute path to the local file (PDF or Office).
            file_type:  Extension string (e.g. 'pdf', 'docx', 'pptx').

        Returns:
            DoclingResult with a list of ParseElement objects.
        """
        if not settings.DOCLING_ENABLED:
            logger.info("Docling is disabled (DOCLING_ENABLED=False). Skipping parse.")
            return DoclingResult(success=True, elements=[])

        try:
            from docling.document_converter import DocumentConverter
        except ImportError:
            logger.warning(
                "Docling is not installed. Returning empty parse result. "
                "Install with: pip install docling"
            )
            return DoclingResult(success=False, error="Docling not installed")

        try:
            converter = DocumentConverter()
            doc_result = converter.convert(file_path)
            doc = doc_result.document

            elements: List[ParseElement] = []
            reading_order = 0

            # Iterate through document items
            for item, level in doc.iterate_items():
                page_no = 1
                bbox = None

                # Extract page number and bounding box when available
                if hasattr(item, "prov") and item.prov:
                    prov = item.prov[0] if isinstance(item.prov, list) else item.prov
                    page_no = getattr(prov, "page_no", 1) or 1
                    bbox = getattr(prov, "bbox", None)

                # Determine page dimensions for normalisation
                page_width, page_height = 612.0, 792.0  # A4 default (points)
                if hasattr(doc, "pages") and doc.pages:
                    page_obj = doc.pages.get(page_no)
                    if page_obj and hasattr(page_obj, "size"):
                        page_width = page_obj.size.width or page_width
                        page_height = page_obj.size.height or page_height

                # Get element label
                label = getattr(item, "label", "text")
                if hasattr(label, "value"):
                    label = label.value
                elem_type = self._detect_element_type(str(label))

                # Extract text content
                content: Optional[str] = None
                if hasattr(item, "text"):
                    content = item.text
                elif hasattr(item, "export_to_markdown"):
                    try:
                        content = item.export_to_markdown()
                    except Exception:
                        pass

                x0, y0, x1, y1 = self._normalize_bbox(bbox, page_width, page_height)

                elements.append(
                    ParseElement(
                        element_type=elem_type,
                        content=content,
                        page_number=page_no,
                        reading_order=reading_order,
                        bbox_x0=x0,
                        bbox_y0=y0,
                        bbox_x1=x1,
                        bbox_y1=y1,
                    )
                )
                reading_order += 1

            page_count = len(doc.pages) if hasattr(doc, "pages") and doc.pages else 1
            logger.info(
                f"Docling parsed '{Path(file_path).name}': "
                f"{len(elements)} elements across {page_count} pages."
            )
            return DoclingResult(elements=elements, page_count=page_count, success=True)

        except Exception as exc:
            logger.error(f"Docling parsing failed for '{file_path}': {exc}")
            return DoclingResult(success=False, error=str(exc))


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_docling_service_instance: Optional[DoclingParserService] = None


def get_docling_service() -> DoclingParserService:
    """Return the process-level DoclingParserService singleton."""
    global _docling_service_instance
    if _docling_service_instance is None:
        _docling_service_instance = DoclingParserService()
    return _docling_service_instance

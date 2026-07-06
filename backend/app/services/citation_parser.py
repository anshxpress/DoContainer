"""
Sprint 4 — Day 2: Citation System Prompt Builder & Parser

Responsibilities:
  1. build_system_prompt()  — constructs the strict instruction prompt for the LLM
  2. validate_citations()   — warns if the answer references non-existent pages
  3. parse_citations()      — extracts structured Citation objects from an answer string
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    doc_name: str
    page_number: int
    paragraph: str = ""
    confidence: float = 1.0


# ─────────────────────────────────────────────────────────────────────────────
# System Prompt Builder
# ─────────────────────────────────────────────────────────────────────────────

def build_system_prompt(page_metadata: List[Dict[str, Any]]) -> str:
    """
    Build a strict system instruction that forces the model to:
      1. Answer ONLY from the provided page images / snippets
      2. Embed inline citations in the format [DocName, Page N]
      3. Never hallucinate information not present in the pages
    """
    pages_description = "\n".join(
        f"  • Document: '{m.get('doc_name', 'Document')}', Page: {m.get('page_number', 1)}"
        f" — Paragraph/Section: '{m.get('hierarchy', 'General')}'"
        f" — Text: \"{m.get('text_snippet', '')[:200]}\""
        for m in page_metadata
    )

    return (
        "You are DoContainer AI, an enterprise document intelligence assistant.\n\n"
        "## Rules you MUST follow:\n"
        "1. Answer ONLY using information visible in the provided context pages.\n"
        "2. Do NOT invent information. If the answer is not in the provided pages, say:\n"
        "   'I could not find relevant information in the provided documents.'\n"
        "3. You must provide a clear, markdown-formatted response.\n"
        "4. AT THE VERY END of your response, you MUST append a line exactly reading '---CITATIONS---' followed by a raw JSON array of citations for the facts you used.\n"
        "   Example format:\n"
        "   Your answer goes here in markdown.\n"
        "   ---CITATIONS---\n"
        "   [\n"
        "     {\n"
        '       "document_name": "Invoice.pdf",\n'
        '       "page": 2,\n'
        '       "paragraph": "Payment Terms",\n'
        '       "confidence": 0.95\n'
        "     }\n"
        "   ]\n"
        "5. Include a confidence score (0.0 to 1.0) for each citation based on how well it answers the query.\n\n"
        "## Available Context Pages:\n"
        f"{pages_description}\n\n"
        "Now answer the user's question based strictly on the above pages."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Citation Validator
# ─────────────────────────────────────────────────────────────────────────────

# Matches patterns like [DocName, Page 5] or [Doc Name.pdf, Page 12]
_CITATION_RE = re.compile(r"\[([^\],]+),\s*Page\s*(\d+)\]", re.IGNORECASE)


def validate_citations(answer: str, page_metadata: List[Dict[str, Any]]) -> List[str]:
    """
    Check that every citation in the answer references a real provided page.
    Returns a list of warning strings for any invalid citations found.
    """
    valid_refs = {
        (m.get("doc_name", "").lower(), int(m.get("page_number", 0)))
        for m in page_metadata
    }

    warnings: List[str] = []
    for match in _CITATION_RE.finditer(answer):
        doc_name = match.group(1).strip().lower()
        page_num = int(match.group(2))
        if (doc_name, page_num) not in valid_refs:
            warnings.append(
                f"Hallucinated citation detected: [{match.group(1).strip()}, Page {page_num}]"
                f" — this page was not in the provided context."
            )
    if warnings:
        for w in warnings:
            logger.warning("Citation validation: %s", w)
    return warnings


# ─────────────────────────────────────────────────────────────────────────────
# Citation Parser
# ─────────────────────────────────────────────────────────────────────────────

def parse_citations(answer: str) -> List[Citation]:
    """
    Extract citations from the JSON array at the end of the answer.
    """
    import json
    citations: List[Citation] = []
    
    parts = answer.split("---CITATIONS---")
    if len(parts) > 1:
        json_str = parts[-1].strip()
        # Clean up markdown code blocks if the model wrapped it
        if json_str.startswith("```json"):
            json_str = json_str.replace("```json", "", 1)
        if json_str.startswith("```"):
            json_str = json_str.replace("```", "", 1)
        if json_str.endswith("```"):
            json_str = json_str[:-3]
        json_str = json_str.strip()
            
        try:
            raw_citations = json.loads(json_str)
            if isinstance(raw_citations, list):
                for c in raw_citations:
                    citations.append(Citation(
                        doc_name=c.get("document_name", "Unknown"),
                        page_number=c.get("page", 1),
                        paragraph=c.get("paragraph", ""),
                        confidence=float(c.get("confidence", 1.0))
                    ))
        except Exception as exc:
            logger.warning("Failed to parse JSON citations: %s\nString was: %s", exc, json_str)
            
    return citations

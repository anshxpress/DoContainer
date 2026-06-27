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
        f"  • [{m.get('doc_name', 'Document')}, Page {m.get('page_number', 1)}]"
        f" — snippet: \"{m.get('text_snippet', '')[:100]}\""
        for m in page_metadata
    )

    return (
        "You are DOCSCOPE AI, an enterprise document intelligence assistant.\n\n"
        "## Rules you MUST follow:\n"
        "1. Answer ONLY using information visible in the provided page images and text snippets below.\n"
        "2. Every claim you make must include an inline citation in this EXACT format: [DocName, Page N]\n"
        "   Example: 'The revenue for Q3 was $4.2M [Quarterly_Report.pdf, Page 5].'\n"
        "3. Do NOT invent information. If the answer is not in the provided pages, say:\n"
        "   'I could not find relevant information in the provided documents.'\n"
        "4. Be concise, professional, and structured (use bullet points when listing multiple facts).\n\n"
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
    Extract all [DocName, Page N] citation tags from an answer string.
    Returns a deduplicated list of Citation objects preserving order.
    """
    seen: set = set()
    citations: List[Citation] = []
    for match in _CITATION_RE.finditer(answer):
        doc_name = match.group(1).strip()
        page_num = int(match.group(2))
        key = (doc_name.lower(), page_num)
        if key not in seen:
            seen.add(key)
            citations.append(Citation(doc_name=doc_name, page_number=page_num))
    return citations

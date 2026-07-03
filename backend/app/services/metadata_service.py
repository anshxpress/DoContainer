"""
Hybrid Pipeline — Metadata Enrichment Service

Uses Gemini Flash to extract structured metadata from the full text of a
document: summary, keywords, named entities, topics, document type, category,
reading time, and complexity score.

Persists results to:
  - document_summaries
  - document_keywords
  - document_entities
  - documents.category / documents.department
"""
from __future__ import annotations

import json
import logging
import math
import re
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.models import (
    Document,
    DocumentEntity,
    DocumentKeyword,
    DocumentSummary,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gemini client helper
# ---------------------------------------------------------------------------

def _call_gemini(prompt: str, document_text: str) -> Optional[str]:
    """
    Call Gemini Flash with a JSON-mode structured prompt.
    Returns the raw response text or None on failure.
    """
    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)

        full_prompt = f"{prompt}\n\n---DOCUMENT TEXT---\n{document_text[:15_000]}"
        response = model.generate_content(full_prompt)
        return response.text if response and response.text else None
    except Exception as exc:
        logger.error(f"Gemini API call failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

def _extract_json(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Extract the first JSON object from an LLM response string."""
    if not text:
        return None
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?", "", text).strip().strip("```")
    # Find the first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Reading time estimator
# ---------------------------------------------------------------------------

def _estimate_reading_time(text: str) -> int:
    """Estimate reading time in minutes assuming 200 wpm average."""
    words = len(text.split())
    return max(1, math.ceil(words / 200))


# ---------------------------------------------------------------------------
# Main enrichment function
# ---------------------------------------------------------------------------

METADATA_PROMPT = """
You are a document analysis assistant. Analyse the document text below and
return a single JSON object with EXACTLY these fields (no extra fields):

{
  "summary": "<2-4 sentence executive summary>",
  "keywords": ["keyword1", "keyword2", ...],        // top 20 most relevant
  "entities": [
    {"text": "<entity text>", "type": "<PERSON|ORG|DATE|MONEY|LOCATION|PRODUCT|LAW>"}
  ],
  "topics": ["<topic1>", "<topic2>"],               // 3-7 high-level topics
  "document_type": "<contract|report|research|invoice|letter|policy|manual|other>",
  "category": "<HR|Finance|Legal|Engineering|Marketing|Operations|Other>",
  "department": "<optional department name or empty string>",
  "complexity_score": <float 0.0 (simple) to 1.0 (highly technical)>,
  "importance_score": <float 1.0 (low) to 10.0 (high) based on business impact>,
  "risk_score": <float 0.0 (safe) to 10.0 (high risk) based on PII, confidentiality, liability>,
  "risk_issues": ["<explanation of risk 1>", "<explanation of risk 2>"], // empty if safe
  "executive_summary": "<A concise, bulleted summary for executives>"
}

Return valid JSON only. No markdown, no commentary.
"""


async def enrich_document_metadata(
    db: Session,
    document_id: str,
    full_text: str,
    org_id: str,
) -> bool:
    """
    Enrich a document with AI-generated metadata.

    Calls Gemini Flash, persists results to:
      - document_summaries (upsert)
      - document_keywords (replace)
      - document_entities (replace)
      - documents.category / .department (update)

    Args:
        db:           SQLAlchemy session.
        document_id:  String UUID of the target document.
        full_text:    Concatenated page text to analyse.
        org_id:       Organisation UUID string.

    Returns:
        True on success, False if Gemini or DB operations fail.
    """
    doc_uuid = uuid.UUID(document_id)
    org_uuid = uuid.UUID(org_id)

    if not full_text or len(full_text.strip()) < 50:
        logger.warning(f"Document {document_id}: insufficient text for metadata enrichment.")
        return False

    # ------------------------------------------------------------------
    # 1. Call Gemini Flash
    # ------------------------------------------------------------------
    raw_response = _call_gemini(METADATA_PROMPT, full_text)
    parsed = _extract_json(raw_response)

    if not parsed:
        logger.warning(
            f"Document {document_id}: Gemini returned unparseable metadata. "
            "Falling back to minimal defaults."
        )
        parsed = {
            "summary": full_text[:500],
            "keywords": [],
            "entities": [],
            "topics": [],
            "document_type": "other",
            "category": "Other",
            "department": "",
            "complexity_score": 0.5,
            "importance_score": 5.0,
            "risk_score": 0.0,
            "risk_issues": [],
            "executive_summary": full_text[:200]
        }

    summary_text = parsed.get("summary", "")
    keywords: List[str] = parsed.get("keywords", [])[:20]
    entities: List[Dict] = parsed.get("entities", [])
    topics: List[str] = parsed.get("topics", [])
    document_type = parsed.get("document_type", "other")
    category = parsed.get("category", "Other")
    department = parsed.get("department", "") or None
    complexity_score = float(parsed.get("complexity_score", 0.5))
    importance_score = float(parsed.get("importance_score", 5.0))
    risk_score = float(parsed.get("risk_score", 0.0))
    risk_issues: List[str] = parsed.get("risk_issues", [])
    executive_summary = parsed.get("executive_summary", "")
    reading_time = _estimate_reading_time(full_text)

    try:
        # ------------------------------------------------------------------
        # 2. Upsert DocumentSummary
        # ------------------------------------------------------------------
        existing_summary = (
            db.query(DocumentSummary)
            .filter(DocumentSummary.document_id == doc_uuid)
            .first()
        )
        if existing_summary:
            existing_summary.summary = summary_text
            existing_summary.reading_time_minutes = reading_time
            existing_summary.complexity_score = complexity_score
            existing_summary.importance_score = importance_score
            existing_summary.risk_score = risk_score
            existing_summary.risk_issues_json = json.dumps(risk_issues)
            existing_summary.executive_summary = executive_summary
            existing_summary.document_type = document_type
            existing_summary.topics_json = json.dumps(topics)
            db.add(existing_summary)
        else:
            db.add(
                DocumentSummary(
                    document_id=doc_uuid,
                    org_id=org_uuid,
                    summary=summary_text,
                    reading_time_minutes=reading_time,
                    complexity_score=complexity_score,
                    importance_score=importance_score,
                    risk_score=risk_score,
                    risk_issues_json=json.dumps(risk_issues),
                    executive_summary=executive_summary,
                    document_type=document_type,
                    topics_json=json.dumps(topics),
                )
            )

        # ------------------------------------------------------------------
        # 3. Replace DocumentKeywords (delete + insert)
        # ------------------------------------------------------------------
        db.query(DocumentKeyword).filter(
            DocumentKeyword.document_id == doc_uuid
        ).delete(synchronize_session=False)

        new_keywords = []
        for idx, kw in enumerate(keywords):
            if kw and isinstance(kw, str):
                new_keywords.append(
                    DocumentKeyword(
                        document_id=doc_uuid,
                        org_id=org_uuid,
                        keyword=kw.strip()[:255],
                        score=round(1.0 - (idx / max(len(keywords), 1)), 4),
                    )
                )
        if new_keywords:
            db.bulk_save_objects(new_keywords)

        # ------------------------------------------------------------------
        # 4. Replace DocumentEntities (delete + insert)
        # ------------------------------------------------------------------
        db.query(DocumentEntity).filter(
            DocumentEntity.document_id == doc_uuid
        ).delete(synchronize_session=False)

        valid_types = {"PERSON", "ORG", "DATE", "MONEY", "LOCATION", "PRODUCT", "LAW"}
        new_entities = []
        for ent in entities:
            ent_text = str(ent.get("text", "")).strip()[:500]
            ent_type = str(ent.get("type", "ORG")).upper()
            if ent_text and ent_type in valid_types:
                new_entities.append(
                    DocumentEntity(
                        document_id=doc_uuid,
                        org_id=org_uuid,
                        entity_text=ent_text,
                        entity_type=ent_type,
                    )
                )
        if new_entities:
            db.bulk_save_objects(new_entities)

        # ------------------------------------------------------------------
        # 5. Update Document.category / .department
        # ------------------------------------------------------------------
        doc = db.query(Document).filter(Document.id == doc_uuid).first()
        if doc:
            doc.category = category
            doc.department = department
            db.add(doc)

        db.commit()
        logger.info(
            f"Metadata enrichment committed for document {document_id}: "
            f"summary={len(summary_text)} chars, keywords={len(keywords)}, "
            f"entities={len(entities)}"
        )
        return True

    except Exception as exc:
        logger.error(f"Failed to persist metadata for document {document_id}: {exc}")
        try:
            db.rollback()
        except Exception:
            pass
        return False

import logging
import uuid
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from celery import shared_task

from backend.app.core.db import SessionLocal
from backend.app.models.models import Document, DocumentEntity, KnowledgeGraphEdge, DocumentSummary
from backend.app.services.bge_service import get_bge_service
from backend.app.core.qdrant import search_text_chunks

logger = logging.getLogger(__name__)

@shared_task(
    name="backend.app.tasks.knowledge_graph_tasks.build_knowledge_graph_task",
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True
)
def build_knowledge_graph_task(self, document_id: str) -> Dict[str, Any]:
    """
    Automated task to link a newly ingested document to existing documents
    in the Knowledge Graph based on shared entities and vector similarity.
    """
    logger.info(f"[build_knowledge_graph_task] Starting for document {document_id}")
    db = SessionLocal()
    edges_created = 0
    try:
        doc_uuid = uuid.UUID(document_id) if isinstance(document_id, str) else document_id
        doc = db.query(Document).filter(Document.id == doc_uuid).first()
        
        if not doc:
            logger.error(f"Document {document_id} not found in DB.")
            return {"status": "failed"}

        # 1. Entity Overlap
        entities = db.query(DocumentEntity).filter(DocumentEntity.document_id == doc_uuid).all()
        entity_texts = {e.entity_text.lower() for e in entities if e.entity_type in ['ORG', 'PERSON', 'PRODUCT']}
        
        if entity_texts:
            # Find other docs in the same org sharing these entities
            shared = db.query(DocumentEntity).filter(
                DocumentEntity.org_id == doc.org_id,
                DocumentEntity.document_id != doc_uuid,
                DocumentEntity.entity_text.in_([e.entity_text for e in entities])
            ).all()
            
            shared_doc_ids = set()
            for s in shared:
                if s.entity_text.lower() in entity_texts:
                    shared_doc_ids.add(s.document_id)
                    
            for target_id in shared_doc_ids:
                edge = KnowledgeGraphEdge(
                    org_id=doc.org_id,
                    source_document_id=doc_uuid,
                    target_document_id=target_id,
                    relationship_type="shared_entity",
                    weight=0.8,
                    metadata_json="{}"
                )
                db.add(edge)
                edges_created += 1

        # 2. Vector Similarity (based on summary)
        summary = db.query(DocumentSummary).filter(DocumentSummary.document_id == doc_uuid).first()
        if summary and summary.summary:
            bge = get_bge_service()
            query_vec = bge.encode_query(summary.summary[:500])
            if query_vec:
                chunks = search_text_chunks(
                    query_vector=query_vec,
                    org_id=str(doc.org_id),
                    team_ids=[],
                    limit=10
                )
                similar_doc_ids = set()
                for chunk in chunks:
                    if chunk.score > 0.85:
                        t_id = chunk.payload.get("document_id")
                        if t_id and t_id != str(doc_uuid):
                            similar_doc_ids.add(uuid.UUID(t_id))
                            
                for target_id in similar_doc_ids:
                    edge = KnowledgeGraphEdge(
                        org_id=doc.org_id,
                        source_document_id=doc_uuid,
                        target_document_id=target_id,
                        relationship_type="similarity",
                        weight=0.85,
                        metadata_json="{}"
                    )
                    db.add(edge)
                    edges_created += 1
                    
        # 3. Topic Overlap
        if summary and summary.topics_json:
            import json
            try:
                topics = set(json.loads(summary.topics_json))
                if topics:
                    other_summaries = db.query(DocumentSummary).filter(
                        DocumentSummary.org_id == doc.org_id,
                        DocumentSummary.document_id != doc_uuid,
                        DocumentSummary.topics_json.isnot(None)
                    ).all()
                    
                    for other in other_summaries:
                        if other.topics_json:
                            other_topics = set(json.loads(other.topics_json))
                            overlap = topics.intersection(other_topics)
                            if len(overlap) >= 1: # Link if they share at least 1 topic
                                edge = KnowledgeGraphEdge(
                                    org_id=doc.org_id,
                                    source_document_id=doc_uuid,
                                    target_document_id=other.document_id,
                                    relationship_type="shared_topic",
                                    weight=min(0.5 + (0.15 * len(overlap)), 1.0),
                                    metadata_json=json.dumps({"shared_topics": list(overlap)})
                                )
                                db.add(edge)
                                edges_created += 1
            except Exception as e:
                logger.warning(f"Error processing topics for KG: {e}")

        db.commit()
        logger.info(f"[build_knowledge_graph_task] Created {edges_created} edges for {document_id}")
        return {"status": "completed", "edges_created": edges_created}
        
    except Exception as exc:
        db.rollback()
        logger.error(f"[build_knowledge_graph_task] Failed: {exc}")
        raise exc
    finally:
        db.close()

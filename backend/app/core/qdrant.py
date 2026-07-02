import logging
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, MultiVectorConfig, MultiVectorComparator,
    PayloadSchemaType, Filter, FieldCondition, MatchValue, MatchAny,
    ScoredPoint
)
from qdrant_client.http.exceptions import UnexpectedResponse

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Qdrant Client
qdrant_client = QdrantClient(url=settings.QDRANT_URL)


def init_text_collection() -> None:
    """
    Hybrid Pipeline: Creates the 'text_chunks' Qdrant collection for BGE-M3
    dense text embeddings (1024-dim, Cosine distance).

    Creates payload indexes on org_id, folder_id, document_id, chunk_type,
    language, and page_number to enable fast filtered searches with
    multi-tenant isolation.

    Idempotent: skips creation if the collection already exists.
    """
    collection_name = settings.QDRANT_TEXT_COLLECTION_NAME

    try:
        if qdrant_client.collection_exists(collection_name):
            logger.info(f"Qdrant text collection '{collection_name}' already exists.")
            return

        logger.info(f"Creating Qdrant text collection '{collection_name}' (BGE-M3, 1024-dim)...")
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=1024,          # BGE-M3 dense output dimension
                distance=Distance.COSINE,
            ),
        )
        logger.info(f"Text collection '{collection_name}' created successfully.")

        # Payload indexes for multi-tenant filtering and search acceleration
        index_fields = [
            ("org_id", PayloadSchemaType.KEYWORD),
            ("folder_id", PayloadSchemaType.KEYWORD),
            ("document_id", PayloadSchemaType.KEYWORD),
            ("chunk_type", PayloadSchemaType.KEYWORD),
            ("language", PayloadSchemaType.KEYWORD),
            ("page_number", PayloadSchemaType.INTEGER),
        ]
        for field_name, field_schema in index_fields:
            qdrant_client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=field_schema,
            )
        logger.info(f"Payload indexes created for text collection '{collection_name}'.")

    except UnexpectedResponse as e:
        logger.warning(
            f"Failed to communicate with Qdrant server at {settings.QDRANT_URL}: {e}. "
            "Skipping text collection initialization."
        )
    except Exception as e:
        logger.error(f"Error initializing Qdrant text collection: {e}")


def init_qdrant_collection() -> None:
    """
    Day 6-7: Qdrant Setup, Configuration, and Multi-Vector Integration.
    Creates the 'pages' collection with MultiVectorConfig and builds
    payload indexes for optimized search performance.
    """
    collection_name = settings.QDRANT_COLLECTION_NAME
    
    try:
        # Check if collection already exists
        exists = qdrant_client.collection_exists(collection_name)
        if exists:
            logger.info(f"Qdrant collection '{collection_name}' already exists.")
            return

        logger.info(f"Creating Qdrant collection '{collection_name}' with Multi-Vector configuration...")
        
        # Create collection with MultiVectorConfig
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=128,  # Multi-vector dimensions (128)
                distance=Distance.COSINE,
                multivector_config=MultiVectorConfig(
                    comparator=MultiVectorComparator.MAX_SIM
                )
            )
        )
        logger.info(f"Collection '{collection_name}' created successfully.")

        # Create payload indexes for multi-tenant isolation and search acceleration
        logger.info("Creating payload indexes for 'org_id', 'folder_id', and 'allowed_teams'...")
        
        qdrant_client.create_payload_index(
            collection_name=collection_name,
            field_name="org_id",
            field_schema=PayloadSchemaType.KEYWORD
        )
        qdrant_client.create_payload_index(
            collection_name=collection_name,
            field_name="folder_id",
            field_schema=PayloadSchemaType.KEYWORD
        )
        qdrant_client.create_payload_index(
            collection_name=collection_name,
            field_name="allowed_teams",
            field_schema=PayloadSchemaType.KEYWORD
        )
        
        logger.info("Qdrant indexes created successfully.")
    except UnexpectedResponse as e:
        # Graceful fallback for local development if Qdrant instance is offline
        logger.warning(f"Failed to communicate with Qdrant server at {settings.QDRANT_URL}: {e}. Skipping initialization.")
    except Exception as e:
        logger.error(f"Error initializing Qdrant collection: {e}")


def search_pages(
    query_vectors: List[List[float]],
    org_id: str,
    team_ids: List[str],
    folder_id: Optional[str] = None,
    document_ids: Optional[List[str]] = None,
    limit: int = 20,
) -> List[ScoredPoint]:
    """
    Day 3: Multi-Vector Semantic Search with Permission Filtering.

    Executes a MaxSim multi-vector query against the Qdrant 'pages' collection,
    filtered to pages the current user is permitted to access.

    Permission filter logic:
      - Must match org_id (hard tenant boundary).
      - Must match folder_id when provided (optional scope narrowing).
      - Must match document_id when provided (optional scope narrowing).
      - Must match at least one of the user's team_ids via MatchAny
        (enforces team-level access control).

    Args:
        query_vectors: Multi-vector query produced by the retriever.
        org_id:        The authenticated user's organisation UUID string.
        team_ids:      List of team UUID strings the user belongs to.
        folder_id:     Optional folder UUID string to narrow the search scope.
        document_id:   Optional document UUID string to narrow the search scope.
        limit:         Maximum number of scored points to return.

    Returns:
        A list of ScoredPoint objects ordered by descending MaxSim score.
        Returns an empty list when Qdrant is unreachable (dev fallback).
    """
    collection_name = settings.QDRANT_COLLECTION_NAME

    # Build must-conditions for tenant isolation
    must_conditions = [
        FieldCondition(key="org_id", match=MatchValue(value=org_id)),
        FieldCondition(key="allowed_teams", match=MatchAny(any=team_ids)),
    ]

    # Narrow to a specific folder when requested
    if folder_id:
        must_conditions.append(
            FieldCondition(key="folder_id", match=MatchValue(value=folder_id))
        )
        
    # Narrow to specific documents when requested
    if document_ids:
        must_conditions.append(
            FieldCondition(key="document_id", match=MatchAny(any=document_ids))
        )

    payload_filter = Filter(must=must_conditions)

    try:
        results = qdrant_client.query_points(
            collection_name=collection_name,
            query=query_vectors,
            query_filter=payload_filter,
            limit=limit,
            with_payload=True,
        )
        return results.points
    except UnexpectedResponse as e:
        logger.warning(
            f"Qdrant search failed (UnexpectedResponse): {e}. Returning empty results."
        )
        return []
    except Exception as e:
        logger.warning(
            f"Qdrant search failed: {e}. Returning empty results for dev fallback."
        )
        return []


def search_text_chunks(
    query_vector: List[float],
    org_id: str,
    team_ids: List[str],
    folder_id: Optional[str] = None,
    document_ids: Optional[List[str]] = None,
    chunk_type: Optional[str] = None,
    language: Optional[str] = None,
    limit: int = 20,
) -> List[ScoredPoint]:
    """
    Hybrid Pipeline: Dense single-vector search over the BGE-M3 'text_chunks'
    Qdrant collection.

    Applies the same multi-tenant permission filter logic as search_pages():
      - Hard org boundary via org_id match.
      - Optional folder_id / document_id scope narrowing.
      - Optional chunk_type / language filtering.

    Note: team_ids are not enforced on the text collection at the vector level
    because chunk payloads carry org_id; folder-level team gating is handled
    by the search service which cross-references DocumentPage ownership.

    Args:
        query_vector:  1024-dim float list produced by BGEM3Service.encode_query().
        org_id:        Authenticated user's organisation UUID string.
        team_ids:      User's team UUID strings (reserved for future use / logging).
        folder_id:     Optional folder UUID string for scope narrowing.
        document_id:   Optional document UUID string for scope narrowing.
        chunk_type:    Optional chunk type filter (paragraph/heading/table/ocr).
        language:      Optional ISO-639-1 language code filter.
        limit:         Maximum results to return.

    Returns:
        List of ScoredPoint objects ordered by descending cosine similarity.
        Returns an empty list when Qdrant is unreachable.
    """
    collection_name = settings.QDRANT_TEXT_COLLECTION_NAME

    must_conditions = [
        FieldCondition(key="org_id", match=MatchValue(value=org_id)),
    ]
    if folder_id:
        must_conditions.append(
            FieldCondition(key="folder_id", match=MatchValue(value=folder_id))
        )
    if document_ids:
        must_conditions.append(
            FieldCondition(key="document_id", match=MatchAny(any=document_ids))
        )
    if chunk_type:
        must_conditions.append(
            FieldCondition(key="chunk_type", match=MatchValue(value=chunk_type))
        )
    if language:
        must_conditions.append(
            FieldCondition(key="language", match=MatchValue(value=language))
        )

    payload_filter = Filter(must=must_conditions)

    try:
        results = qdrant_client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=payload_filter,
            limit=limit,
            with_payload=True,
        )
        return results.points
    except UnexpectedResponse as e:
        logger.warning(
            f"text_chunks search failed (UnexpectedResponse): {e}. Returning empty results."
        )
        return []
    except Exception as e:
        logger.warning(
            f"text_chunks search failed: {e}. Returning empty results for dev fallback."
        )
        return []

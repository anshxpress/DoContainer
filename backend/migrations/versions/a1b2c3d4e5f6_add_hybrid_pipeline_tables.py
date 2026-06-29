"""add_hybrid_pipeline_tables

Revision ID: a1b2c3d4e5f6
Revises: 9e8a56f2d2b5
Create Date: 2026-06-29 12:00:00.000000

Adds 7 new tables for the Hybrid OCR + BGE-M3 + Vision RAG pipeline:
  - document_parse_elements  (Docling structured elements)
  - ocr_chunks               (PaddleOCR recognised text regions)
  - text_embedding_chunks    (BGE-M3 Qdrant pointers)
  - document_summaries       (Gemini Flash-generated summaries)
  - document_keywords        (LLM-ranked keywords)
  - document_entities        (Named entities: PERSON, ORG, DATE…)
  - processing_jobs          (Per-task status tracker for the dashboard)

Also adds two nullable columns to 'documents':
  - category   (inferred document category)
  - department (inferred owning department)

All changes are non-destructive. No existing tables or columns are altered.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9e8a56f2d2b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Extend 'documents' with metadata enrichment columns
    # ------------------------------------------------------------------
    # Guard: only add if not already present (idempotent for re-runs)
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    doc_columns = [c["name"] for c in inspector.get_columns("documents")]

    if "category" not in doc_columns:
        op.add_column(
            "documents",
            sa.Column("category", sa.String(255), nullable=True),
        )
    if "department" not in doc_columns:
        op.add_column(
            "documents",
            sa.Column("department", sa.String(255), nullable=True),
        )

    # ------------------------------------------------------------------
    # 2. document_parse_elements — Docling structural elements
    # ------------------------------------------------------------------
    op.create_table(
        "document_parse_elements",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "document_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("org_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("element_type", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("reading_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("bbox_x0", sa.Float(), nullable=True),
        sa.Column("bbox_y0", sa.Float(), nullable=True),
        sa.Column("bbox_x1", sa.Float(), nullable=True),
        sa.Column("bbox_y1", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_document_parse_elements_document_id",
        "document_parse_elements",
        ["document_id"],
    )
    op.create_index(
        "ix_document_parse_elements_org_id",
        "document_parse_elements",
        ["org_id"],
    )

    # ------------------------------------------------------------------
    # 3. ocr_chunks — PaddleOCR recognised text regions
    # ------------------------------------------------------------------
    op.create_table(
        "ocr_chunks",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "document_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("org_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("bbox_x0", sa.Float(), nullable=True),
        sa.Column("bbox_y0", sa.Float(), nullable=True),
        sa.Column("bbox_x1", sa.Float(), nullable=True),
        sa.Column("bbox_y1", sa.Float(), nullable=True),
        sa.Column("reading_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_ocr_chunks_document_id", "ocr_chunks", ["document_id"])
    op.create_index("ix_ocr_chunks_org_id", "ocr_chunks", ["org_id"])

    # ------------------------------------------------------------------
    # 4. text_embedding_chunks — BGE-M3 Qdrant text_chunks pointers
    # ------------------------------------------------------------------
    op.create_table(
        "text_embedding_chunks",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "document_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("org_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("folder_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_type", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("qdrant_point_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_text_embedding_chunks_document_id",
        "text_embedding_chunks",
        ["document_id"],
    )
    op.create_index(
        "ix_text_embedding_chunks_org_id",
        "text_embedding_chunks",
        ["org_id"],
    )

    # ------------------------------------------------------------------
    # 5. document_summaries — Gemini Flash summaries (one per document)
    # ------------------------------------------------------------------
    op.create_table(
        "document_summaries",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "document_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("org_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("reading_time_minutes", sa.Integer(), nullable=True),
        sa.Column("complexity_score", sa.Float(), nullable=True),
        sa.Column("language", sa.String(10), nullable=True),
        sa.Column("document_type", sa.String(100), nullable=True),
        sa.Column("topics_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_document_summaries_document_id",
        "document_summaries",
        ["document_id"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # 6. document_keywords
    # ------------------------------------------------------------------
    op.create_table(
        "document_keywords",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "document_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("org_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("keyword", sa.String(255), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_document_keywords_document_id", "document_keywords", ["document_id"]
    )
    op.create_index("ix_document_keywords_org_id", "document_keywords", ["org_id"])

    # ------------------------------------------------------------------
    # 7. document_entities
    # ------------------------------------------------------------------
    op.create_table(
        "document_entities",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "document_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("org_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_text", sa.String(500), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_document_entities_document_id", "document_entities", ["document_id"]
    )
    op.create_index("ix_document_entities_org_id", "document_entities", ["org_id"])

    # ------------------------------------------------------------------
    # 8. processing_jobs — Per-task Celery status tracker
    # ------------------------------------------------------------------
    op.create_table(
        "processing_jobs",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "document_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("org_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.String(100), nullable=False),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_processing_jobs_document_id", "processing_jobs", ["document_id"]
    )
    op.create_index("ix_processing_jobs_org_id", "processing_jobs", ["org_id"])


def downgrade() -> None:
    op.drop_table("processing_jobs")
    op.drop_table("document_entities")
    op.drop_table("document_keywords")
    op.drop_table("document_summaries")
    op.drop_table("text_embedding_chunks")
    op.drop_table("ocr_chunks")
    op.drop_table("document_parse_elements")

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    doc_columns = [c["name"] for c in inspector.get_columns("documents")]
    if "department" in doc_columns:
        op.drop_column("documents", "department")
    if "category" in doc_columns:
        op.drop_column("documents", "category")

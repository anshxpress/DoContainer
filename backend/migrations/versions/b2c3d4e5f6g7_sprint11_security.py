"""Sprint 11 Security

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-03 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. document_versions
    op.create_table('document_versions',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, default=1),
        sa.Column('s3_key', sa.String(length=1024), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('uploader_id', sa.UUID(), nullable=True),
        sa.Column('change_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploader_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', 'version_number', name='uq_doc_version')
    )
    op.create_index(op.f('ix_document_versions_document_id'), 'document_versions', ['document_id'], unique=False)
    op.create_index(op.f('ix_document_versions_org_id'), 'document_versions', ['org_id'], unique=False)

    # 2. document_acls
    op.create_table('document_acls',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('principal_type', sa.String(length=20), nullable=False),
        sa.Column('principal_id', sa.UUID(), nullable=False),
        sa.Column('permission', sa.String(length=50), nullable=False),
        sa.Column('granted_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['granted_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', 'principal_type', 'principal_id', 'permission', name='uq_doc_acl_entry')
    )
    op.create_index(op.f('ix_document_acls_document_id'), 'document_acls', ['document_id'], unique=False)
    op.create_index(op.f('ix_document_acls_org_id'), 'document_acls', ['org_id'], unique=False)
    op.create_index(op.f('ix_document_acls_principal_id'), 'document_acls', ['principal_id'], unique=False)

    # 3. document_locks
    op.create_table('document_locks',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('locked_by', sa.UUID(), nullable=False),
        sa.Column('locked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('lock_reason', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['locked_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_locks_document_id'), 'document_locks', ['document_id'], unique=True)

    # 4. approval_requests
    op.create_table('approval_requests',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=False),
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('submitted_by', sa.UUID(), nullable=False),
        sa.Column('reviewed_by', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('submission_note', sa.Text(), nullable=True),
        sa.Column('review_note', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['submitted_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_approval_requests_document_id'), 'approval_requests', ['document_id'], unique=False)
    op.create_index(op.f('ix_approval_requests_org_id'), 'approval_requests', ['org_id'], unique=False)

    # 5. retention_policies
    op.create_table('retention_policies',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('folder_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('retain_days', sa.Integer(), nullable=False),
        sa.Column('auto_delete', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['folder_id'], ['folders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_retention_policies_org_id'), 'retention_policies', ['org_id'], unique=False)

    # 6. document_watermarks
    op.create_table('document_watermarks',
        sa.Column('id', sa.UUID(), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('document_id', sa.UUID(), nullable=True),
        sa.Column('folder_id', sa.UUID(), nullable=True),
        sa.Column('org_id', sa.UUID(), nullable=False),
        sa.Column('watermark_text', sa.String(length=255), nullable=False),
        sa.Column('include_username', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('include_timestamp', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('opacity', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['folder_id'], ['folders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_document_watermarks_document_id'), 'document_watermarks', ['document_id'], unique=True)
    op.create_index(op.f('ix_document_watermarks_org_id'), 'document_watermarks', ['org_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_document_watermarks_org_id'), table_name='document_watermarks')
    op.drop_index(op.f('ix_document_watermarks_document_id'), table_name='document_watermarks')
    op.drop_table('document_watermarks')
    
    op.drop_index(op.f('ix_retention_policies_org_id'), table_name='retention_policies')
    op.drop_table('retention_policies')
    
    op.drop_index(op.f('ix_approval_requests_org_id'), table_name='approval_requests')
    op.drop_index(op.f('ix_approval_requests_document_id'), table_name='approval_requests')
    op.drop_table('approval_requests')
    
    op.drop_index(op.f('ix_document_locks_document_id'), table_name='document_locks')
    op.drop_table('document_locks')
    
    op.drop_index(op.f('ix_document_acls_principal_id'), table_name='document_acls')
    op.drop_index(op.f('ix_document_acls_org_id'), table_name='document_acls')
    op.drop_index(op.f('ix_document_acls_document_id'), table_name='document_acls')
    op.drop_table('document_acls')
    
    op.drop_index(op.f('ix_document_versions_org_id'), table_name='document_versions')
    op.drop_index(op.f('ix_document_versions_document_id'), table_name='document_versions')
    op.drop_table('document_versions')

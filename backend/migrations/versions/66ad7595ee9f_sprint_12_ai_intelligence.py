"""Sprint 12 AI Intelligence

Revision ID: 66ad7595ee9f
Revises: b2c3d4e5f6g7
Create Date: 2026-07-03 23:43:01.950713

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '66ad7595ee9f'
down_revision: Union[str, None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('document_summaries', sa.Column('importance_score', sa.Float(), nullable=True))
    op.add_column('document_summaries', sa.Column('risk_score', sa.Float(), nullable=True))
    op.add_column('document_summaries', sa.Column('risk_issues_json', sa.Text(), nullable=True))
    op.add_column('document_summaries', sa.Column('executive_summary', sa.Text(), nullable=True))
    op.add_column('document_summaries', sa.Column('entities_json', sa.Text(), nullable=True))
    op.add_column('document_summaries', sa.Column('key_dates_json', sa.Text(), nullable=True))
    op.add_column('document_summaries', sa.Column('confidence_score', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('document_summaries', 'confidence_score')
    op.drop_column('document_summaries', 'key_dates_json')
    op.drop_column('document_summaries', 'entities_json')
    op.drop_column('document_summaries', 'executive_summary')
    op.drop_column('document_summaries', 'risk_issues_json')
    op.drop_column('document_summaries', 'risk_score')
    op.drop_column('document_summaries', 'importance_score')

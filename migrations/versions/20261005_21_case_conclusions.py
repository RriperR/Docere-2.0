"""Неизменяемые версии итога клинического случая.

Revision ID: 20261005_21
Revises: 20261005_20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = '20261005_21'
down_revision = '20261005_20'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Создать версии без копирования исходных медицинских документов."""
    op.create_table(
        'case_conclusions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('case_id', sa.Uuid(), sa.ForeignKey('clinical_cases.id'), nullable=False),
        sa.Column('number', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('findings', sa.Text(), nullable=False),
        sa.Column('next_actions', sa.Text(), nullable=False),
        sa.Column('source_ids', JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('case_id', 'number', name='uq_case_conclusion_version'),
    )
    op.create_index('ix_case_conclusions_case_id', 'case_conclusions', ['case_id'])


def downgrade() -> None:
    """Удалить версии случаев; опубликованные медицинские записи остаются."""
    op.drop_table('case_conclusions')

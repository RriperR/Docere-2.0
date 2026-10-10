"""Личные незавершённые тексты клинического разбора.

Revision ID: 20261010_23
Revises: 20261005_22
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = '20261010_23'
down_revision = '20261005_22'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавить личные формы без изменения опубликованного контекста."""
    op.create_table(
        'case_work_drafts',
        sa.Column('case_id', sa.Uuid(), sa.ForeignKey('clinical_cases.id'), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('kind', sa.String(16), primary_key=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('content', sa.JSON().with_variant(JSONB(), 'postgresql'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_case_work_drafts_expires_at', 'case_work_drafts', ['expires_at'])


def downgrade() -> None:
    """Удалить только незавершённые формы; сообщения и итоги сохраняются."""
    op.drop_index('ix_case_work_drafts_expires_at', table_name='case_work_drafts')
    op.drop_table('case_work_drafts')

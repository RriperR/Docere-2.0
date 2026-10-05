"""Обсуждение, запросы мнения и журнал разбора.

Revision ID: 20261005_20
Revises: 20261005_19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = '20261005_20'
down_revision = '20261005_19'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Создать отдельное от комментариев записей обсуждение."""
    op.create_table(
        'case_messages',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('case_id', sa.Uuid(), sa.ForeignKey('clinical_cases.id'), nullable=False),
        sa.Column('author_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('idempotency_key', sa.Uuid(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('parent_id', sa.Uuid(), sa.ForeignKey('case_messages.id')),
        sa.Column('record_id', sa.Uuid(), sa.ForeignKey('medical_records.id')),
        sa.Column('attachment_id', sa.Uuid(), sa.ForeignKey('file_attachments.id')),
        sa.Column('opinion_id', sa.Uuid()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('case_id', 'author_id', 'idempotency_key', name='uq_case_message_retry'),
    )
    op.create_index('ix_case_messages_case_id', 'case_messages', ['case_id'])
    op.create_table(
        'case_opinions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('case_id', sa.Uuid(), sa.ForeignKey('clinical_cases.id'), nullable=False),
        sa.Column('requester_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('assignee_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('record_id', sa.Uuid(), sa.ForeignKey('medical_records.id')),
        sa.Column('reason', sa.String(64)),
        sa.Column('response_message_id', sa.Uuid(), sa.ForeignKey('case_messages.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_case_opinions_case_id', 'case_opinions', ['case_id'])
    op.create_table(
        'case_events',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('case_id', sa.Uuid(), sa.ForeignKey('clinical_cases.id'), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(32), nullable=False),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('subject_id', sa.Uuid()),
        sa.Column('recipients', JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('case_id', 'sequence', name='uq_case_event_sequence'),
    )
    op.create_index('ix_case_events_case_id', 'case_events', ['case_id'])


def downgrade() -> None:
    """Удалить только таблицы нового обсуждения."""
    op.drop_table('case_events')
    op.drop_table('case_opinions')
    op.drop_table('case_messages')

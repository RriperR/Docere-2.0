"""Личные сводки материалов случая и транзакционная фоновая доставка."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = '20261011_25'
down_revision = '20261011_24'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавить запуски без изменения материалов, обсуждений и итогов."""
    op.create_table(
        'case_summary_runs',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('case_id', sa.Uuid(), sa.ForeignKey('clinical_cases.id'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('idempotency_key', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('model', sa.String(255), nullable=False),
        sa.Column('provider', sa.String(255), nullable=False),
        sa.Column('prompt_version', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.Column('next_delivery_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('delivery_attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('processing_token', sa.Uuid()),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True)),
        sa.Column('options_json', sa.JSON().with_variant(JSONB(), 'postgresql'), nullable=False),
        sa.Column('sources_json', sa.JSON().with_variant(JSONB(), 'postgresql'), nullable=False),
        sa.Column('documents_json', sa.JSON().with_variant(JSONB(), 'postgresql'), nullable=False),
        sa.UniqueConstraint('case_id', 'user_id', 'idempotency_key', name='uq_case_summary_key'),
    )
    op.create_index(
        'uq_case_summary_active',
        'case_summary_runs',
        ['case_id', 'user_id'],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_index('ix_case_summary_delivery', 'case_summary_runs', ['status', 'next_delivery_at'])


def downgrade() -> None:
    """Удалить AI-сводки, сохранив медицинскую историю и все клинические случаи."""
    op.drop_index('ix_case_summary_delivery', table_name='case_summary_runs')
    op.drop_index('uq_case_summary_active', table_name='case_summary_runs')
    op.drop_table('case_summary_runs')

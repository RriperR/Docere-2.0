"""Надёжная доставка импорта и владение обработкой.

Revision ID: 20261004_17
Revises: 20260627_16
"""

import sqlalchemy as sa
from alembic import op

revision = '20261004_17'
down_revision = '20260627_16'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавить outbox, версии статусов и lease; восстановить старые задания."""
    op.add_column('import_jobs', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('import_jobs', sa.Column('processing_token', sa.Uuid(), nullable=True))
    op.add_column('import_jobs', sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        'import_dispatch',
        sa.Column('job_id', sa.Uuid(), sa.ForeignKey('import_jobs.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('request_id', sa.String(128), nullable=True),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('ix_import_dispatch_next_attempt_at', 'import_dispatch', ['next_attempt_at'])
    op.execute(
        'INSERT INTO import_dispatch (job_id, next_attempt_at) SELECT id, CURRENT_TIMESTAMP FROM import_jobs '
        "WHERE status IN ('queued', 'running')"
    )


def downgrade() -> None:
    """Удалить инфраструктуру доставки; выполнять только после остановки обработчиков."""
    op.drop_table('import_dispatch')
    op.drop_column('import_jobs', 'lease_expires_at')
    op.drop_column('import_jobs', 'processing_token')
    op.drop_column('import_jobs', 'version')

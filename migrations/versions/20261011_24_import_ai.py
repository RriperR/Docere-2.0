"""AI-запуски импорта и независимые результаты документов."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = '20261011_24'
down_revision = '20261010_23'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Создать таблицы без изменения существующих импортов."""
    op.create_table(
        'import_ai_runs',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('job_id', sa.Uuid(), sa.ForeignKey('import_jobs.id'), nullable=False),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('idempotency_key', sa.Uuid(), nullable=False),
        sa.Column('selection_hash', sa.String(64), nullable=False),
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
        sa.UniqueConstraint('job_id', 'idempotency_key', name='uq_import_ai_run_key'),
    )
    op.create_index(
        'uq_import_ai_active_job',
        'import_ai_runs',
        ['job_id'],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_index('ix_import_ai_delivery', 'import_ai_runs', ['status', 'next_delivery_at'])
    op.create_table(
        'import_ai_documents',
        sa.Column('run_id', sa.Uuid(), sa.ForeignKey('import_ai_runs.id'), primary_key=True),
        sa.Column('file_id', sa.String(64), primary_key=True),
        sa.Column('path', sa.String(1024), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('mime_type', sa.String(255), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('page_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('checksum', sa.String(64)),
        sa.Column('result_json', sa.JSON().with_variant(JSONB(), 'postgresql'), nullable=False),
        sa.Column('error_code', sa.String(64)),
        sa.Column('usage_json', sa.JSON(), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    """Удалить предложения AI, сохранив медицинские записи и их provenance."""
    op.drop_table('import_ai_documents')
    op.drop_index('ix_import_ai_delivery', table_name='import_ai_runs')
    op.drop_index('uq_import_ai_active_job', table_name='import_ai_runs')
    op.drop_table('import_ai_runs')

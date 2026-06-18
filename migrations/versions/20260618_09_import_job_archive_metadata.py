"""Add archive metadata to import jobs.

Revision ID: 20260618_09
Revises: 20260618_08
Create Date: 2026-06-18 00:00:09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '20260618_09'
down_revision = '20260618_08'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply archive metadata columns."""
    op.add_column('import_jobs', sa.Column('original_filename', sa.String(length=255), nullable=True))
    op.add_column('import_jobs', sa.Column('archive_storage_key', sa.String(length=512), nullable=True))
    op.add_column('import_jobs', sa.Column('size_bytes', sa.Integer(), nullable=True))
    op.create_index('ix_import_jobs_uploaded_by_user_id', 'import_jobs', ['uploaded_by_user_id'])


def downgrade() -> None:
    """Remove archive metadata columns."""
    op.drop_index('ix_import_jobs_uploaded_by_user_id', table_name='import_jobs')
    op.drop_column('import_jobs', 'size_bytes')
    op.drop_column('import_jobs', 'archive_storage_key')
    op.drop_column('import_jobs', 'original_filename')

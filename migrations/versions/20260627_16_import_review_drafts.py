"""Add server-side drafts for archive import review.

Revision ID: 20260627_16
Revises: 20260627_15
Create Date: 2026-06-27 00:00:16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '20260627_16'
down_revision = '20260627_15'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add review decisions and their last update timestamp."""
    op.add_column('import_jobs', sa.Column('review_decisions_json', sa.JSON(), nullable=True))
    op.add_column('import_jobs', sa.Column('review_updated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Remove server-side import review drafts."""
    op.drop_column('import_jobs', 'review_updated_at')
    op.drop_column('import_jobs', 'review_decisions_json')

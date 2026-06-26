"""Add optional expiration for record sharing.

Revision ID: 20260626_13
Revises: 20260619_12
Create Date: 2026-06-26 00:00:13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '20260626_13'
down_revision = '20260619_12'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable expiration timestamps; existing access stays unlimited."""
    op.add_column('record_share_requests', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('user_record_links', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Remove optional expiration timestamps."""
    op.drop_column('user_record_links', 'expires_at')
    op.drop_column('record_share_requests', 'expires_at')

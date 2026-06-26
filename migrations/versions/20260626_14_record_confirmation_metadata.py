"""Add confirmation metadata to medical records.

Revision ID: 20260626_14
Revises: 20260626_13
Create Date: 2026-06-26 00:00:14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260626_14'
down_revision = '20260626_13'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable confirmation metadata for future confirmations."""
    op.add_column('medical_records', sa.Column('confirmed_by_user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('medical_records', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(
        'fk_medical_records_confirmed_by_user_id',
        'medical_records',
        'users',
        ['confirmed_by_user_id'],
        ['id'],
    )


def downgrade() -> None:
    """Remove confirmation metadata."""
    op.drop_constraint('fk_medical_records_confirmed_by_user_id', 'medical_records', type_='foreignkey')
    op.drop_column('medical_records', 'confirmed_at')
    op.drop_column('medical_records', 'confirmed_by_user_id')

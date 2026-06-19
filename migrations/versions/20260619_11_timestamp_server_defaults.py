"""Add timestamp server defaults.

Revision ID: 20260619_11
Revises: 20260618_10
Create Date: 2026-06-19 00:00:11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '20260619_11'
down_revision = '20260618_10'
branch_labels = None
depends_on = None


_TIMESTAMP_DEFAULTS: tuple[tuple[str, str], ...] = (
    ('users', 'created_at'),
    ('users', 'updated_at'),
    ('patient_passports', 'created_at'),
    ('patient_passports', 'updated_at'),
    ('medical_records', 'created_at'),
    ('medical_records', 'updated_at'),
    ('file_attachments', 'uploaded_at'),
    ('import_jobs', 'created_at'),
    ('audit_events', 'created_at'),
    ('user_record_links', 'created_at'),
    ('practitioner_passports', 'created_at'),
    ('practitioner_passports', 'updated_at'),
    ('record_comments', 'created_at'),
    ('record_share_requests', 'created_at'),
    ('record_shares', 'created_at'),
)


def upgrade() -> None:
    """Apply server defaults for ORM-managed timestamp columns."""
    for table_name, column_name in _TIMESTAMP_DEFAULTS:
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
        )


def downgrade() -> None:
    """Remove timestamp server defaults."""
    for table_name, column_name in reversed(_TIMESTAMP_DEFAULTS):
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.DateTime(timezone=True),
            server_default=None,
        )

"""Add server-side defaults for creation timestamps.

Revision ID: 20260618_06
Revises: 20260421_05
Create Date: 2026-06-18 00:00:06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '20260618_06'
down_revision = '20260421_05'
branch_labels = None
depends_on = None

# Колонки-таймстампы создания, которым проставляется серверный дефолт now().
_TIMESTAMP_COLUMNS = (
    ('users', 'created_at'),
    ('users', 'updated_at'),
    ('medical_records', 'created_at'),
    ('medical_records', 'updated_at'),
    ('patient_passports', 'created_at'),
    ('patient_passports', 'updated_at'),
    ('practitioner_passports', 'created_at'),
    ('practitioner_passports', 'updated_at'),
    ('record_comments', 'created_at'),
    ('record_share_requests', 'created_at'),
    ('record_shares', 'created_at'),
    ('file_attachments', 'uploaded_at'),
    ('user_record_links', 'created_at'),
)


def upgrade() -> None:
    for table_name, column_name in _TIMESTAMP_COLUMNS:
        op.alter_column(table_name, column_name, server_default=sa.text('now()'))


def downgrade() -> None:
    for table_name, column_name in _TIMESTAMP_COLUMNS:
        op.alter_column(table_name, column_name, server_default=None)

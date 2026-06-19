"""Add ImportJob needs_review status.

Revision ID: 20260619_12
Revises: 20260619_11
Create Date: 2026-06-19 00:00:12
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260619_12'
down_revision = '20260619_11'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add needs_review to import_job_status enum."""
    op.execute("ALTER TYPE import_job_status ADD VALUE IF NOT EXISTS 'needs_review'")


def downgrade() -> None:
    """Keep enum value on downgrade because PostgreSQL cannot drop it safely."""

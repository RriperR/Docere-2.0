"""Add audit event indexes.

Revision ID: 20260618_10
Revises: 20260618_09
Create Date: 2026-06-18 00:00:10
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = '20260618_10'
down_revision = '20260618_09'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply audit indexes."""
    op.create_index('ix_audit_events_event_type', 'audit_events', ['event_type'])
    op.create_index('ix_audit_events_entity_type', 'audit_events', ['entity_type'])
    op.create_index('ix_audit_events_entity_id', 'audit_events', ['entity_id'])


def downgrade() -> None:
    """Remove audit indexes."""
    op.drop_index('ix_audit_events_entity_id', table_name='audit_events')
    op.drop_index('ix_audit_events_entity_type', table_name='audit_events')
    op.drop_index('ix_audit_events_event_type', table_name='audit_events')

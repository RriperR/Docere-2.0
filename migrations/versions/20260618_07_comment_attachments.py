"""Add comment_id and filename to file attachments.

Revision ID: 20260618_07
Revises: 20260618_06
Create Date: 2026-06-18 00:00:07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '20260618_07'
down_revision = '20260618_06'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('file_attachments', sa.Column('comment_id', sa.Uuid(), nullable=True))
    op.add_column('file_attachments', sa.Column('filename', sa.String(length=255), nullable=True))
    op.create_index('ix_file_attachments_comment_id', 'file_attachments', ['comment_id'])
    op.create_foreign_key(
        'fk_file_attachments_comment_id_record_comments',
        'file_attachments',
        'record_comments',
        ['comment_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_file_attachments_comment_id_record_comments', 'file_attachments', type_='foreignkey')
    op.drop_index('ix_file_attachments_comment_id', table_name='file_attachments')
    op.drop_column('file_attachments', 'filename')
    op.drop_column('file_attachments', 'comment_id')

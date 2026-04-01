"""Add practitioner passports, record comments, and richer medical records.

Revision ID: 20260401_04
Revises: 20260311_03
Create Date: 2026-04-01 00:00:04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260401_04'
down_revision = '20260311_03'
branch_labels = None
depends_on = None

practitioner_passport_status = postgresql.ENUM(
    'draft',
    'confirmed',
    name='practitioner_passport_status',
    create_type=False,
)
file_attachment_category = postgresql.ENUM(
    'lab',
    'imaging',
    'document',
    'other',
    name='file_attachment_category',
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    practitioner_passport_status.create(bind, checkfirst=True)
    file_attachment_category.create(bind, checkfirst=True)

    op.create_table(
        'practitioner_passports',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('specialty', sa.String(length=255), nullable=True),
        sa.Column('organization', sa.String(length=255), nullable=True),
        sa.Column('position', sa.String(length=255), nullable=True),
        sa.Column('email', sa.String(length=320), nullable=True),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('status', practitioner_passport_status, nullable=False, server_default='draft'),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_practitioner_passports_created_by_user_id',
        'practitioner_passports',
        ['created_by_user_id'],
        unique=False,
    )
    op.create_index('ix_practitioner_passports_user_id', 'practitioner_passports', ['user_id'], unique=False)

    op.add_column(
        'medical_records',
        sa.Column('author_practitioner_passport_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        'medical_records',
        sa.Column('appointment_location', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'medical_records',
        sa.Column('clinical_summary', sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        'fk_medical_records_author_practitioner_passport_id',
        'medical_records',
        'practitioner_passports',
        ['author_practitioner_passport_id'],
        ['id'],
    )
    op.create_index(
        'ix_medical_records_author_practitioner_passport_id',
        'medical_records',
        ['author_practitioner_passport_id'],
        unique=False,
    )

    op.create_table(
        'record_comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('author_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['author_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['record_id'], ['medical_records.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_record_comments_record_id', 'record_comments', ['record_id'], unique=False)
    op.create_index('ix_record_comments_author_user_id', 'record_comments', ['author_user_id'], unique=False)

    op.add_column(
        'file_attachments',
        sa.Column('uploaded_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        'file_attachments',
        sa.Column('category', file_attachment_category, nullable=True),
    )
    op.create_foreign_key(
        'fk_file_attachments_uploaded_by_user_id',
        'file_attachments',
        'users',
        ['uploaded_by_user_id'],
        ['id'],
    )
    op.create_index(
        'ix_file_attachments_uploaded_by_user_id',
        'file_attachments',
        ['uploaded_by_user_id'],
        unique=False,
    )

    op.execute(
        "UPDATE file_attachments SET category = 'other'::file_attachment_category WHERE category IS NULL",
    )
    op.alter_column('file_attachments', 'category', nullable=False)


def downgrade() -> None:
    op.drop_index('ix_file_attachments_uploaded_by_user_id', table_name='file_attachments')
    op.drop_constraint('fk_file_attachments_uploaded_by_user_id', 'file_attachments', type_='foreignkey')
    op.drop_column('file_attachments', 'category')
    op.drop_column('file_attachments', 'uploaded_by_user_id')

    op.drop_index('ix_record_comments_author_user_id', table_name='record_comments')
    op.drop_index('ix_record_comments_record_id', table_name='record_comments')
    op.drop_table('record_comments')

    op.drop_index(
        'ix_medical_records_author_practitioner_passport_id',
        table_name='medical_records',
    )
    op.drop_constraint(
        'fk_medical_records_author_practitioner_passport_id',
        'medical_records',
        type_='foreignkey',
    )
    op.drop_column('medical_records', 'clinical_summary')
    op.drop_column('medical_records', 'appointment_location')
    op.drop_column('medical_records', 'author_practitioner_passport_id')

    op.drop_index('ix_practitioner_passports_user_id', table_name='practitioner_passports')
    op.drop_index('ix_practitioner_passports_created_by_user_id', table_name='practitioner_passports')
    op.drop_table('practitioner_passports')

    op.execute('DROP TYPE IF EXISTS file_attachment_category')
    op.execute('DROP TYPE IF EXISTS practitioner_passport_status')

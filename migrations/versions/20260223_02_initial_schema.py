"""initial schema

Revision ID: 20260223_02
Revises: 20260223_01
Create Date: 2026-02-23 00:00:01

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260223_02'
down_revision = '20260223_01'
branch_labels = None
depends_on = None


user_role = sa.Enum('patient', 'doctor', 'lab_technician', 'admin', name='user_role')
user_status = sa.Enum('active', 'blocked', name='user_status')
record_status = sa.Enum('draft', 'unconfirmed', 'confirmed', 'rejected', name='record_status')
record_type = sa.Enum('consultation_result', 'exam_result', 'lab_result', 'other', name='record_type')
share_status = sa.Enum('pending', 'accepted', 'rejected', name='share_status')
access_source = sa.Enum('self_created', 'share_accepted', 'imported', name='access_source')
import_job_status = sa.Enum(
    'queued',
    'running',
    'completed',
    'failed',
    'completed_with_warnings',
    name='import_job_status',
)


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fio', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', user_role, nullable=False),
        sa.Column('status', user_status, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_users_email'),
    )

    op.create_table(
        'patients',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('linked_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('fio', sa.String(length=255), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('email', sa.String(length=320), nullable=True),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['linked_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('linked_user_id', name='uq_patients_linked_user_id'),
    )
    op.create_index('ix_patients_date_of_birth', 'patients', ['date_of_birth'], unique=False)

    op.create_table(
        'medical_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('creator_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', record_status, nullable=False),
        sa.Column('record_type', record_type, nullable=False),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('payload_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['creator_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_medical_records_patient_id', 'medical_records', ['patient_id'], unique=False)

    op.create_table(
        'record_shares',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('granted_by_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('granted_to_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', share_status, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['granted_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['granted_to_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['record_id'], ['medical_records.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_record_shares_record_id', 'record_shares', ['record_id'], unique=False)

    op.create_table(
        'user_patient_access',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source', access_source, nullable=False),
        sa.Column('source_record_share_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id']),
        sa.ForeignKeyConstraint(['source_record_share_id'], ['record_shares.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'patient_id', name='uq_user_patient_access_user_patient'),
    )
    op.create_index('ix_user_patient_access_user_id', 'user_patient_access', ['user_id'], unique=False)
    op.create_index(
        'ix_user_patient_access_patient_id',
        'user_patient_access',
        ['patient_id'],
        unique=False,
    )

    op.create_table(
        'file_attachments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('storage_key', sa.String(length=512), nullable=False),
        sa.Column('mime_type', sa.String(length=255), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['record_id'], ['medical_records.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('storage_key', name='uq_file_attachments_storage_key'),
    )
    op.create_index('ix_file_attachments_record_id', 'file_attachments', ['record_id'], unique=False)

    op.create_table(
        'import_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('uploaded_by_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', import_job_status, nullable=False),
        sa.Column('report_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('event_type', sa.String(length=128), nullable=False),
        sa.Column('entity_type', sa.String(length=128), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('audit_events')
    op.drop_table('import_jobs')
    op.drop_index('ix_file_attachments_record_id', table_name='file_attachments')
    op.drop_table('file_attachments')
    op.drop_index('ix_user_patient_access_patient_id', table_name='user_patient_access')
    op.drop_index('ix_user_patient_access_user_id', table_name='user_patient_access')
    op.drop_table('user_patient_access')
    op.drop_index('ix_record_shares_record_id', table_name='record_shares')
    op.drop_table('record_shares')
    op.drop_index('ix_medical_records_patient_id', table_name='medical_records')
    op.drop_table('medical_records')
    op.drop_index('ix_patients_date_of_birth', table_name='patients')
    op.drop_table('patients')
    op.drop_table('users')

    op.execute('DROP TYPE IF EXISTS import_job_status')
    op.execute('DROP TYPE IF EXISTS access_source')
    op.execute('DROP TYPE IF EXISTS share_status')
    op.execute('DROP TYPE IF EXISTS record_type')
    op.execute('DROP TYPE IF EXISTS record_status')
    op.execute('DROP TYPE IF EXISTS user_status')
    op.execute('DROP TYPE IF EXISTS user_role')

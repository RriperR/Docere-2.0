"""Перевод схемы БД на PatientPassport и UserRecordLink.

Revision ID: 20260311_03
Revises: 20260223_02
Create Date: 2026-03-11 00:00:03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260311_03'
down_revision = '20260223_02'
branch_labels = None
depends_on = None

patient_passport_status = postgresql.ENUM(
    'draft',
    'confirmed',
    name='patient_passport_status',
    create_type=False,
)
record_link_source = postgresql.ENUM(
    'creator',
    'share_accepted',
    'imported',
    'manual_attach',
    name='record_link_source',
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    patient_passport_status.create(bind, checkfirst=True)
    record_link_source.create(bind, checkfirst=True)

    op.rename_table('patients', 'patient_passports')
    op.drop_constraint('uq_patients_linked_user_id', 'patient_passports', type_='unique')
    op.alter_column('patient_passports', 'linked_user_id', new_column_name='patient_user_id')
    op.add_column(
        'patient_passports',
        sa.Column('status', patient_passport_status, nullable=False, server_default='draft'),
    )
    op.add_column(
        'patient_passports',
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE patient_passports
        SET status = CASE
            WHEN patient_user_id IS NULL THEN 'draft'::patient_passport_status
            ELSE 'confirmed'::patient_passport_status
        END,
        confirmed_at = CASE
            WHEN patient_user_id IS NULL THEN NULL
            ELSE created_at
        END
        """,
    )
    op.alter_column('patient_passports', 'status', server_default=None)
    op.drop_index('ix_patients_date_of_birth', table_name='patient_passports')
    op.create_index(
        'ix_patient_passports_date_of_birth',
        'patient_passports',
        ['date_of_birth'],
        unique=False,
    )
    op.create_index(
        'ix_patient_passports_patient_user_id',
        'patient_passports',
        ['patient_user_id'],
        unique=False,
    )

    op.drop_index('ix_medical_records_patient_id', table_name='medical_records')
    op.execute('ALTER TABLE medical_records DROP CONSTRAINT IF EXISTS medical_records_patient_id_fkey')
    op.drop_column('medical_records', 'patient_id')
    op.alter_column('medical_records', 'title', existing_type=sa.String(length=255), nullable=True)
    op.create_index('ix_medical_records_event_date', 'medical_records', ['event_date'], unique=False)

    op.drop_index('ix_user_patient_access_patient_id', table_name='user_patient_access')
    op.drop_index('ix_user_patient_access_user_id', table_name='user_patient_access')
    op.drop_table('user_patient_access')
    op.execute('DROP TYPE IF EXISTS access_source')

    op.create_table(
        'user_record_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_passport_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source', record_link_source, nullable=False),
        sa.Column('source_record_share_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['record_id'], ['medical_records.id']),
        sa.ForeignKeyConstraint(['patient_passport_id'], ['patient_passports.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_user_record_links_user_id', 'user_record_links', ['user_id'], unique=False)
    op.create_index('ix_user_record_links_record_id', 'user_record_links', ['record_id'], unique=False)
    op.create_index(
        'ix_user_record_links_patient_passport_id',
        'user_record_links',
        ['patient_passport_id'],
        unique=False,
    )


def downgrade() -> None:
    access_source = postgresql.ENUM(
        'self_created',
        'share_accepted',
        'imported',
        name='access_source',
        create_type=False,
    )
    bind = op.get_bind()
    access_source.create(bind, checkfirst=True)

    op.drop_index('ix_user_record_links_patient_passport_id', table_name='user_record_links')
    op.drop_index('ix_user_record_links_record_id', table_name='user_record_links')
    op.drop_index('ix_user_record_links_user_id', table_name='user_record_links')
    op.drop_table('user_record_links')

    op.drop_index('ix_patient_passports_patient_user_id', table_name='patient_passports')
    op.drop_index('ix_patient_passports_date_of_birth', table_name='patient_passports')
    op.create_index('ix_patients_date_of_birth', 'patient_passports', ['date_of_birth'], unique=False)
    op.drop_column('patient_passports', 'confirmed_at')
    op.drop_column('patient_passports', 'status')
    op.alter_column('patient_passports', 'patient_user_id', new_column_name='linked_user_id')
    op.create_unique_constraint('uq_patients_linked_user_id', 'patient_passports', ['linked_user_id'])
    op.rename_table('patient_passports', 'patients')

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

    op.drop_index('ix_medical_records_event_date', table_name='medical_records')
    op.add_column('medical_records', sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(
        'ALTER TABLE medical_records ADD CONSTRAINT medical_records_patient_id_fkey '
        'FOREIGN KEY(patient_id) REFERENCES patients (id)',
    )
    op.create_index('ix_medical_records_patient_id', 'medical_records', ['patient_id'], unique=False)
    op.alter_column('medical_records', 'title', existing_type=sa.String(length=255), nullable=False)

    op.execute('DROP TYPE IF EXISTS record_link_source')
    op.execute('DROP TYPE IF EXISTS patient_passport_status')

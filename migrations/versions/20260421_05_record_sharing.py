"""Add record sharing requests.

Revision ID: 20260421_05
Revises: 20260401_04
Create Date: 2026-04-21 00:00:05
"""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260421_05'
down_revision = '20260401_04'
branch_labels = None
depends_on = None

record_share_status = postgresql.ENUM(
    'pending',
    'accepted',
    'declined',
    'cancelled',
    'revoked',
    name='record_share_status',
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    record_share_status.create(bind, checkfirst=True)

    op.drop_index('ix_record_shares_record_id', table_name='record_shares')
    op.rename_table('record_shares', 'legacy_record_shares')

    op.create_table(
        'record_share_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('from_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('to_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', record_share_status, nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['from_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['to_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_record_share_requests_from_user_id', 'record_share_requests', ['from_user_id'])
    op.create_index('ix_record_share_requests_to_user_id', 'record_share_requests', ['to_user_id'])

    op.create_table(
        'record_shares',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('record_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_passport_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', record_share_status, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['patient_passport_id'], ['patient_passports.id']),
        sa.ForeignKeyConstraint(['record_id'], ['medical_records.id']),
        sa.ForeignKeyConstraint(['request_id'], ['record_share_requests.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_record_shares_patient_passport_id', 'record_shares', ['patient_passport_id'])
    op.create_index('ix_record_shares_record_id', 'record_shares', ['record_id'])
    op.create_index('ix_record_shares_request_id', 'record_shares', ['request_id'])

    legacy_rows = bind.execute(
        sa.text(
            """
            SELECT
                id,
                record_id,
                granted_by_user_id,
                granted_to_user_id,
                status::text AS status,
                created_at,
                responded_at
            FROM legacy_record_shares
            """,
        ),
    ).mappings()
    for legacy_row in legacy_rows:
        request_id = uuid4()
        new_status = 'declined' if legacy_row['status'] == 'rejected' else legacy_row['status']
        responded_at = legacy_row['responded_at'] if new_status in {'accepted', 'declined'} else None
        patient_passport_id = bind.execute(
            sa.text(
                """
                SELECT patient_passport_id
                FROM user_record_links
                WHERE record_id = :record_id
                ORDER BY created_at ASC
                LIMIT 1
                """,
            ),
            {'record_id': legacy_row['record_id']},
        ).scalar()

        bind.execute(
            sa.text(
                """
                INSERT INTO record_share_requests (
                    id,
                    from_user_id,
                    to_user_id,
                    status,
                    message,
                    created_at,
                    responded_at,
                    cancelled_at,
                    revoked_at
                )
                VALUES (
                    :id,
                    :from_user_id,
                    :to_user_id,
                    CAST(:status AS record_share_status),
                    NULL,
                    :created_at,
                    :responded_at,
                    NULL,
                    NULL
                )
                """,
            ),
            {
                'id': request_id,
                'from_user_id': legacy_row['granted_by_user_id'],
                'to_user_id': legacy_row['granted_to_user_id'],
                'status': new_status,
                'created_at': legacy_row['created_at'],
                'responded_at': responded_at,
            },
        )
        bind.execute(
            sa.text(
                """
                INSERT INTO record_shares (
                    id,
                    request_id,
                    record_id,
                    patient_passport_id,
                    status,
                    created_at,
                    responded_at,
                    revoked_at
                )
                VALUES (
                    :id,
                    :request_id,
                    :record_id,
                    :patient_passport_id,
                    CAST(:status AS record_share_status),
                    :created_at,
                    :responded_at,
                    NULL
                )
                """,
            ),
            {
                'id': legacy_row['id'],
                'request_id': request_id,
                'record_id': legacy_row['record_id'],
                'patient_passport_id': patient_passport_id,
                'status': new_status,
                'created_at': legacy_row['created_at'],
                'responded_at': responded_at,
            },
        )

    op.drop_table('legacy_record_shares')
    op.execute('DROP TYPE IF EXISTS share_status')

    op.create_foreign_key(
        'fk_user_record_links_source_record_share_id',
        'user_record_links',
        'record_shares',
        ['source_record_share_id'],
        ['id'],
    )


def downgrade() -> None:
    share_status = postgresql.ENUM(
        'pending',
        'accepted',
        'rejected',
        name='share_status',
        create_type=False,
    )
    bind = op.get_bind()

    op.drop_constraint(
        'fk_user_record_links_source_record_share_id',
        'user_record_links',
        type_='foreignkey',
    )

    share_status.create(bind, checkfirst=True)
    op.create_table(
        'legacy_record_shares',
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
    bind.execute(
        sa.text(
            """
            INSERT INTO legacy_record_shares (
                id,
                record_id,
                granted_by_user_id,
                granted_to_user_id,
                status,
                created_at,
                responded_at
            )
            SELECT
                shares.id,
                shares.record_id,
                requests.from_user_id,
                requests.to_user_id,
                CAST(
                    CASE
                        WHEN shares.status::text IN ('pending', 'accepted') THEN shares.status::text
                        ELSE 'rejected'
                    END
                    AS share_status
                ),
                shares.created_at,
                COALESCE(
                    shares.responded_at,
                    requests.responded_at,
                    requests.cancelled_at,
                    requests.revoked_at
                )
            FROM record_shares AS shares
            JOIN record_share_requests AS requests ON requests.id = shares.request_id
            """,
        ),
    )

    op.drop_index('ix_record_shares_request_id', table_name='record_shares')
    op.drop_index('ix_record_shares_record_id', table_name='record_shares')
    op.drop_index('ix_record_shares_patient_passport_id', table_name='record_shares')
    op.drop_table('record_shares')

    op.drop_index('ix_record_share_requests_to_user_id', table_name='record_share_requests')
    op.drop_index('ix_record_share_requests_from_user_id', table_name='record_share_requests')
    op.drop_table('record_share_requests')

    op.execute('DROP TYPE IF EXISTS record_share_status')
    op.rename_table('legacy_record_shares', 'record_shares')
    op.create_index('ix_record_shares_record_id', 'record_shares', ['record_id'], unique=False)

"""Restrict record statuses and add access uniqueness.

Revision ID: 20260618_08
Revises: 20260618_07
Create Date: 2026-06-18 00:00:08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260618_08'
down_revision = '20260618_07'
branch_labels = None
depends_on = None

new_record_status = postgresql.ENUM(
    'unconfirmed',
    'confirmed',
    name='record_status_new',
    create_type=False,
)

old_record_status = postgresql.ENUM(
    'draft',
    'unconfirmed',
    'confirmed',
    'rejected',
    name='record_status_old',
    create_type=False,
)


def upgrade() -> None:
    """Apply record status and access uniqueness constraints."""
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            DELETE FROM user_record_links AS duplicate
            USING user_record_links AS original
            WHERE duplicate.id > original.id
              AND duplicate.user_id = original.user_id
              AND duplicate.record_id = original.record_id
              AND (
                    duplicate.patient_passport_id = original.patient_passport_id
                    OR (
                        duplicate.patient_passport_id IS NULL
                        AND original.patient_passport_id IS NULL
                    )
              )
            """,
        ),
    )

    new_record_status.create(bind, checkfirst=True)
    bind.execute(
        sa.text(
            """
            ALTER TABLE medical_records
            ALTER COLUMN status TYPE record_status_new
            USING (
                CASE
                    WHEN status::text = 'confirmed' THEN 'confirmed'
                    ELSE 'unconfirmed'
                END
            )::record_status_new
            """,
        ),
    )
    bind.execute(sa.text('DROP TYPE record_status'))
    bind.execute(sa.text('ALTER TYPE record_status_new RENAME TO record_status'))

    op.create_index(
        'uq_user_record_links_user_record_patient',
        'user_record_links',
        ['user_id', 'record_id', 'patient_passport_id'],
        unique=True,
        postgresql_where=sa.text('patient_passport_id IS NOT NULL'),
    )
    op.create_index(
        'uq_user_record_links_user_record_null_patient',
        'user_record_links',
        ['user_id', 'record_id'],
        unique=True,
        postgresql_where=sa.text('patient_passport_id IS NULL'),
    )


def downgrade() -> None:
    """Restore previous record statuses and remove access uniqueness constraints."""
    bind = op.get_bind()

    op.drop_index('uq_user_record_links_user_record_null_patient', table_name='user_record_links')
    op.drop_index('uq_user_record_links_user_record_patient', table_name='user_record_links')

    old_record_status.create(bind, checkfirst=True)
    bind.execute(
        sa.text(
            """
            ALTER TABLE medical_records
            ALTER COLUMN status TYPE record_status_old
            USING status::text::record_status_old
            """,
        ),
    )
    bind.execute(sa.text('DROP TYPE record_status'))
    bind.execute(sa.text('ALTER TYPE record_status_old RENAME TO record_status'))

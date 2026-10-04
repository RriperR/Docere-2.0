"""Добавить отсутствующие индексы поиска по создателю.

Revision ID: 20261005_18
Revises: 20261004_17
"""

from alembic import op

revision = '20261005_18'
down_revision = '20261004_17'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавить индексы без изменения авторства существующих данных."""
    op.create_index('ix_medical_records_creator_user_id', 'medical_records', ['creator_user_id'])
    op.create_index('ix_patient_passports_created_by_user_id', 'patient_passports', ['created_by_user_id'])


def downgrade() -> None:
    """Удалить только индексы, созданные этой миграцией."""
    op.drop_index('ix_patient_passports_created_by_user_id', table_name='patient_passports')
    op.drop_index('ix_medical_records_creator_user_id', table_name='medical_records')

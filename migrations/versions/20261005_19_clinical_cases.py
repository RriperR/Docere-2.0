"""Клинические случаи и независимое происхождение прав.

Revision ID: 20261005_19
Revises: 20261005_18
"""

from collections import deque
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision = '20261005_19'
down_revision = '20261005_18'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Создать разборы, сохранив независимые источники доступа."""
    op.create_table(
        'clinical_cases',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('patient_id', sa.Uuid(), sa.ForeignKey('patient_passports.id'), nullable=False),
        sa.Column('coordinator_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('previous_case_id', sa.Uuid(), sa.ForeignKey('clinical_cases.id')),
        sa.Column('published_record_id', sa.Uuid(), sa.ForeignKey('medical_records.id')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_clinical_cases_coordinator_id', 'clinical_cases', ['coordinator_id'])
    op.create_index('ix_clinical_cases_status', 'clinical_cases', ['status'])
    op.add_column('record_share_requests', sa.Column('clinical_case_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_share_case', 'record_share_requests', 'clinical_cases', ['clinical_case_id'], ['id'])
    op.create_index('ix_record_share_requests_clinical_case_id', 'record_share_requests', ['clinical_case_id'])
    op.add_column('user_record_links', sa.Column('clinical_case_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_link_case', 'user_record_links', 'clinical_cases', ['clinical_case_id'], ['id'])
    op.create_index('ix_user_record_links_clinical_case_id', 'user_record_links', ['clinical_case_id'])
    for name, columns, condition in (
        (
            'uq_user_record_links_user_record_patient',
            ['user_id', 'record_id', 'patient_passport_id'],
            'patient_passport_id IS NOT NULL',
        ),
        ('uq_user_record_links_user_record_null_patient', ['user_id', 'record_id'], 'patient_passport_id IS NULL'),
    ):
        op.drop_index(name, table_name='user_record_links')
        op.create_index(
            name,
            'user_record_links',
            columns,
            unique=True,
            postgresql_where=sa.text(condition + ' AND clinical_case_id IS NULL'),
        )
    op.create_index(
        'uq_record_link_case', 'user_record_links', ['user_id', 'record_id', 'clinical_case_id'], unique=True
    )
    op.create_table(
        'case_materials',
        sa.Column('case_id', sa.Uuid(), sa.ForeignKey('clinical_cases.id'), primary_key=True),
        sa.Column('record_id', sa.Uuid(), sa.ForeignKey('medical_records.id'), primary_key=True),
    )
    op.create_table(
        'case_members',
        sa.Column('case_id', sa.Uuid(), sa.ForeignKey('clinical_cases.id'), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('share_request_id', sa.Uuid(), sa.ForeignKey('record_share_requests.id')),
        sa.Column('read_sequence', sa.Integer(), nullable=False),
        sa.UniqueConstraint('share_request_id', name='uq_case_member_share'),
    )
    op.create_index('ix_case_members_user_id', 'case_members', ['user_id'])


def downgrade() -> None:
    """Удалить только права случаев; независимые права остаются."""
    _revoke_case_rights()
    op.drop_table('case_members')
    op.drop_table('case_materials')
    op.execute(
        'DELETE FROM record_shares WHERE request_id IN '
        '(SELECT id FROM record_share_requests WHERE clinical_case_id IS NOT NULL)'
    )
    op.execute('DELETE FROM record_share_requests WHERE clinical_case_id IS NOT NULL')
    op.drop_index('uq_record_link_case', table_name='user_record_links')
    for name, columns, condition in (
        (
            'uq_user_record_links_user_record_patient',
            ['user_id', 'record_id', 'patient_passport_id'],
            'patient_passport_id IS NOT NULL',
        ),
        ('uq_user_record_links_user_record_null_patient', ['user_id', 'record_id'], 'patient_passport_id IS NULL'),
    ):
        op.drop_index(name, table_name='user_record_links')
        op.create_index(name, 'user_record_links', columns, unique=True, postgresql_where=sa.text(condition))
    op.drop_index('ix_user_record_links_clinical_case_id', table_name='user_record_links')
    op.drop_constraint('fk_link_case', 'user_record_links', type_='foreignkey')
    op.drop_column('user_record_links', 'clinical_case_id')
    op.drop_index('ix_record_share_requests_clinical_case_id', table_name='record_share_requests')
    op.drop_constraint('fk_share_case', 'record_share_requests', type_='foreignkey')
    op.drop_column('record_share_requests', 'clinical_case_id')
    op.drop_table('clinical_cases')


def _revoke_case_rights() -> None:
    """Отозвать источники случая и зависимые ветви перед удалением новой подсистемы."""
    connection = op.get_bind()
    pairs = connection.execute(
        sa.text('SELECT DISTINCT user_id, record_id FROM user_record_links WHERE clinical_case_id IS NOT NULL')
    ).all()
    connection.execute(sa.text('DELETE FROM user_record_links WHERE clinical_case_id IS NOT NULL'))
    queue: deque[tuple[UUID, UUID]] = deque((row[0], row[1]) for row in pairs)
    visited: set[tuple[UUID, UUID]] = set()
    while queue:
        user_id, record_id = queue.popleft()
        if (user_id, record_id) in visited:
            continue
        visited.add((user_id, record_id))
        params = {'user_id': user_id, 'record_id': record_id}
        independent = connection.scalar(
            sa.text(
                'SELECT EXISTS(SELECT 1 FROM user_record_links WHERE user_id=:user_id '
                'AND record_id=:record_id AND (expires_at IS NULL OR expires_at > now()))'
            ),
            params,
        )
        if independent:
            continue
        downstream = connection.execute(
            sa.text(
                'SELECT s.id, s.request_id, r.to_user_id FROM record_shares s '
                'JOIN record_share_requests r ON r.id=s.request_id '
                "WHERE r.from_user_id=:user_id AND s.record_id=:record_id AND s.status IN ('pending','accepted')"
            ),
            params,
        ).all()
        for share_id, request_id, recipient in downstream:
            connection.execute(
                sa.text('DELETE FROM user_record_links WHERE source_record_share_id=:share_id'),
                {'share_id': share_id},
            )
            connection.execute(
                sa.text("UPDATE record_shares SET status='revoked', revoked_at=now() WHERE id=:share_id"),
                {'share_id': share_id},
            )
            connection.execute(
                sa.text(
                    "UPDATE record_share_requests SET status='revoked', revoked_at=now() WHERE id=:request_id "
                    'AND NOT EXISTS(SELECT 1 FROM record_shares WHERE request_id=:request_id '
                    "AND status IN ('pending','accepted'))"
                ),
                {'request_id': request_id},
            )
            queue.append((recipient, record_id))

"""Outbox уведомлений и позиции прочтения обсуждения.

Revision ID: 20261005_22
Revises: 20261005_21
"""

import sqlalchemy as sa
from alembic import op

revision = '20261005_22'
down_revision = '20261005_21'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Сохранить существующие события для последующей надёжной доставки."""
    op.add_column('case_events', sa.Column('delivered_at', sa.DateTime(timezone=True)))
    op.add_column(
        'case_events',
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.add_column('case_events', sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'))
    op.alter_column('case_events', 'next_attempt_at', server_default=None)
    op.alter_column('case_events', 'attempts', server_default=None)
    op.create_index(
        'ix_case_event_pending', 'case_events', ['next_attempt_at'], postgresql_where=sa.text('delivered_at IS NULL')
    )
    op.create_table(
        'case_notifications',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('event_id', sa.Uuid(), sa.ForeignKey('case_events.id'), nullable=False),
        sa.Column('recipient_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('event_id', 'recipient_id', name='uq_case_notification_delivery'),
    )
    op.create_index('ix_case_notifications_recipient_id', 'case_notifications', ['recipient_id'])
    op.create_table(
        'case_discussion_reads',
        sa.Column('case_id', sa.Uuid(), sa.ForeignKey('clinical_cases.id'), primary_key=True),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('sequence', sa.Integer(), nullable=False),
    )
    op.execute(
        'INSERT INTO case_discussion_reads (case_id, user_id, sequence) '
        'SELECT case_id,user_id,read_sequence FROM case_members'
    )


def downgrade() -> None:
    """Удалить уведомления, сохранив исходный журнал действий."""
    op.drop_table('case_discussion_reads')
    op.drop_table('case_notifications')
    op.drop_index('ix_case_event_pending', table_name='case_events')
    op.drop_column('case_events', 'attempts')
    op.drop_column('case_events', 'next_attempt_at')
    op.drop_column('case_events', 'delivered_at')

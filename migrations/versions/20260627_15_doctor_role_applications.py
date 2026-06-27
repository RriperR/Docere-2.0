"""Add doctor role application workflow.

Revision ID: 20260627_15
Revises: 20260626_14
Create Date: 2026-06-27 00:00:15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '20260627_15'
down_revision = '20260626_14'
branch_labels = None
depends_on = None

application_status = postgresql.ENUM(
    'pending',
    'approved',
    'rejected',
    name='doctor_role_application_status',
    create_type=False,
)
review_status = postgresql.ENUM(
    'pending',
    'approved',
    'rejected',
    name='doctor_role_review_status',
    create_type=False,
)


def upgrade() -> None:
    """Create applications and per-reviewer decisions."""
    bind = op.get_bind()
    application_status.create(bind, checkfirst=True)
    review_status.create(bind, checkfirst=True)
    op.create_table(
        'doctor_role_applications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('applicant_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('specialty', sa.String(length=255), nullable=False),
        sa.Column('status', application_status, server_default='pending', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['applicant_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_doctor_role_applications_applicant_user_id', 'doctor_role_applications', ['applicant_user_id'])
    op.create_index('ix_doctor_role_applications_specialty', 'doctor_role_applications', ['specialty'])
    op.create_index('ix_doctor_role_applications_status', 'doctor_role_applications', ['status'])
    op.create_index(
        'uq_doctor_role_applications_pending_applicant',
        'doctor_role_applications',
        ['applicant_user_id'],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_table(
        'doctor_role_reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('application_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reviewer_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reviewer_role', sa.String(length=32), nullable=False),
        sa.Column('reviewer_specialty', sa.String(length=255), nullable=True),
        sa.Column('status', review_status, server_default='pending', nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['application_id'], ['doctor_role_applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('application_id', 'reviewer_user_id', name='uq_doctor_role_review_reviewer'),
    )
    op.create_index('ix_doctor_role_reviews_application_id', 'doctor_role_reviews', ['application_id'])
    op.create_index('ix_doctor_role_reviews_reviewer_user_id', 'doctor_role_reviews', ['reviewer_user_id'])
    op.create_index('ix_doctor_role_reviews_status', 'doctor_role_reviews', ['status'])


def downgrade() -> None:
    """Drop doctor role application workflow."""
    op.drop_index('ix_doctor_role_reviews_status', table_name='doctor_role_reviews')
    op.drop_index('ix_doctor_role_reviews_reviewer_user_id', table_name='doctor_role_reviews')
    op.drop_index('ix_doctor_role_reviews_application_id', table_name='doctor_role_reviews')
    op.drop_table('doctor_role_reviews')
    op.drop_index('uq_doctor_role_applications_pending_applicant', table_name='doctor_role_applications')
    op.drop_index('ix_doctor_role_applications_status', table_name='doctor_role_applications')
    op.drop_index('ix_doctor_role_applications_specialty', table_name='doctor_role_applications')
    op.drop_index('ix_doctor_role_applications_applicant_user_id', table_name='doctor_role_applications')
    op.drop_table('doctor_role_applications')
    bind = op.get_bind()
    review_status.drop(bind, checkfirst=True)
    application_status.drop(bind, checkfirst=True)

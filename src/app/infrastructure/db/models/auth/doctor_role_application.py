"""ORM-модели заявок пациентов на роль врача."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, func, Index, String, Text, text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.entities.doctor_role_application import (
    DoctorRoleApplicationStatus,
    DoctorRoleReviewStatus,
)
from app.infrastructure.db.base import Base
from app.infrastructure.db.models._enums import enum_values


class DoctorRoleApplicationRow(Base):
    """ORM-представление заявки на роль врача."""

    __tablename__ = 'doctor_role_applications'
    __table_args__ = (
        Index(
            'uq_doctor_role_applications_pending_applicant',
            'applicant_user_id',
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    applicant_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), index=True)
    specialty: Mapped[str] = mapped_column(String(length=255), index=True)
    status: Mapped[DoctorRoleApplicationStatus] = mapped_column(
        Enum(
            DoctorRoleApplicationStatus,
            name='doctor_role_application_status',
            native_enum=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=DoctorRoleApplicationStatus.PENDING,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DoctorRoleReviewRow(Base):
    """ORM-представление решения выбранного проверяющего."""

    __tablename__ = 'doctor_role_reviews'
    __table_args__ = (UniqueConstraint('application_id', 'reviewer_user_id', name='uq_doctor_role_review_reviewer'),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('doctor_role_applications.id', ondelete='CASCADE'),
        index=True,
    )
    reviewer_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), index=True)
    reviewer_role: Mapped[str] = mapped_column(String(length=32))
    reviewer_specialty: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    status: Mapped[DoctorRoleReviewStatus] = mapped_column(
        Enum(
            DoctorRoleReviewStatus,
            name='doctor_role_review_status',
            native_enum=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=DoctorRoleReviewStatus.PENDING,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

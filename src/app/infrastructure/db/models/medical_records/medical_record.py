"""ORM-модель медицинской записи."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum, ForeignKey, func, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.entities.medical_record import MedicalRecordStatus, MedicalRecordType
from app.infrastructure.db.base import Base
from app.infrastructure.db.models._enums import enum_values
from app.infrastructure.db.models._time import utc_now


class MedicalRecordRow(Base):
    """ORM-представление таблицы `medical_records`."""

    __tablename__ = 'medical_records'

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    creator_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), index=True)
    author_practitioner_passport_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('practitioner_passports.id'),
        nullable=True,
        index=True,
    )
    status: Mapped[MedicalRecordStatus] = mapped_column(
        Enum(
            MedicalRecordStatus,
            name='record_status',
            native_enum=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=MedicalRecordStatus.UNCONFIRMED,
    )
    record_type: Mapped[MedicalRecordType] = mapped_column(
        Enum(
            MedicalRecordType,
            name='record_type',
            native_enum=True,
            validate_strings=True,
            values_callable=enum_values,
        )
    )
    event_date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    appointment_location: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    clinical_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON)
    confirmed_by_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=utc_now,
    )

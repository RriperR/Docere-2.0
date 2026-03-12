"""ORM-модель медицинской записи."""

from __future__ import annotations

from datetime import date, datetime, UTC
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.user import _enum_values


def _utc_now() -> datetime:
    """Вернуть текущее время в UTC.

    Returns:
        Текущее время в часовом поясе UTC.
    """
    return datetime.now(tz=UTC)


class MedicalRecordStatusRow(StrEnum):
    """Статусы ORM-модели медицинской записи."""

    DRAFT = 'draft'
    UNCONFIRMED = 'unconfirmed'
    CONFIRMED = 'confirmed'
    REJECTED = 'rejected'


class MedicalRecordTypeRow(StrEnum):
    """Типы ORM-модели медицинской записи."""

    CONSULTATION_RESULT = 'consultation_result'
    EXAM_RESULT = 'exam_result'
    LAB_RESULT = 'lab_result'
    OTHER = 'other'


class MedicalRecordRow(Base):
    """ORM-представление таблицы `medical_records`."""

    __tablename__ = 'medical_records'

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    creator_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('users.id'),
        index=True,
    )
    status: Mapped[MedicalRecordStatusRow] = mapped_column(
        Enum(
            MedicalRecordStatusRow,
            name='record_status',
            native_enum=True,
            validate_strings=True,
            values_callable=_enum_values,
        ),
        default=MedicalRecordStatusRow.UNCONFIRMED,
    )
    record_type: Mapped[MedicalRecordTypeRow] = mapped_column(
        Enum(
            MedicalRecordTypeRow,
            name='record_type',
            native_enum=True,
            validate_strings=True,
            values_callable=_enum_values,
        )
    )
    event_date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        onupdate=_utc_now,
    )

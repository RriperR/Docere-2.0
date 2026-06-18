"""ORM-модель паспортных данных пациента."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum, ForeignKey, func, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models._enums import enum_values
from app.infrastructure.db.models._time import utc_now


class PatientPassportStatusRow(StrEnum):
    """Статусы ORM-модели паспортной карточки."""

    DRAFT = 'draft'
    CONFIRMED = 'confirmed'


class PatientPassportRow(Base):
    """ORM-представление таблицы `patient_passports`."""

    __tablename__ = 'patient_passports'

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('users.id'),
        index=True,
    )
    patient_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('users.id'),
        nullable=True,
        index=True,
    )
    fio: Mapped[str] = mapped_column(String(length=255))
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(length=320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(length=32), nullable=True)
    status: Mapped[PatientPassportStatusRow] = mapped_column(
        Enum(
            PatientPassportStatusRow,
            name='patient_passport_status',
            native_enum=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=PatientPassportStatusRow.DRAFT,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=utc_now,
    )

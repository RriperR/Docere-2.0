"""ORM-модель паспорта врача."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.auth.user import _enum_values


class PractitionerPassportStatusRow(StrEnum):
    """Статусы ORM-модели паспорта врача."""

    DRAFT = 'draft'
    CONFIRMED = 'confirmed'


class PractitionerPassportRow(Base):
    """ORM-представление таблицы `practitioner_passports`."""

    __tablename__ = 'practitioner_passports'

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('users.id'),
        nullable=True,
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('users.id'),
        nullable=True,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(length=255))
    specialty: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    position: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(length=320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(length=32), nullable=True)
    status: Mapped[PractitionerPassportStatusRow] = mapped_column(
        Enum(
            PractitionerPassportStatusRow,
            name='practitioner_passport_status',
            native_enum=True,
            validate_strings=True,
            values_callable=_enum_values,
        ),
        default=PractitionerPassportStatusRow.DRAFT,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

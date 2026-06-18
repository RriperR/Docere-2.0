"""ORM-модель пользователя и связанные enum-типы."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models._enums import enum_values
from app.infrastructure.db.models._time import utc_now


class UserRole(StrEnum):
    """Доступные роли пользователя."""

    PATIENT = 'patient'
    DOCTOR = 'doctor'
    ADMIN = 'admin'


class UserStatus(StrEnum):
    """Статусы учетной записи пользователя."""

    ACTIVE = 'active'
    BLOCKED = 'blocked'


class UserRow(Base):
    """ORM-представление таблицы `users`."""

    __tablename__ = 'users'

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    fio: Mapped[str] = mapped_column(String(length=255))
    email: Mapped[str] = mapped_column(String(length=320), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(length=32))
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(length=255))
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name='user_role',
            native_enum=True,
            validate_strings=True,
            values_callable=enum_values,
        )
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name='user_status',
            native_enum=True,
            validate_strings=True,
            values_callable=enum_values,
        )
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

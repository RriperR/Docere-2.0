from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Enum, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


class UserRole(StrEnum):
    PATIENT = 'patient'
    DOCTOR = 'doctor'
    LAB_TECHNICIAN = 'lab_technician'
    ADMIN = 'admin'


class UserStatus(StrEnum):
    ACTIVE = 'active'
    BLOCKED = 'blocked'


def _enum_values(enum_class: type[StrEnum]) -> list[str]:
    return [item.value for item in enum_class]


class UserRow(Base):
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
            values_callable=_enum_values,
        )
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name='user_status',
            native_enum=True,
            validate_strings=True,
            values_callable=_enum_values,
        )
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        onupdate=_utc_now,
    )

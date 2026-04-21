"""ORM-модели запросов на sharing медицинских записей."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models._time import moscow_now
from app.infrastructure.db.models.auth.user import _enum_values


class RecordShareStatusRow(StrEnum):
    """Статусы запроса и отдельных записей в sharing-flow."""

    PENDING = 'pending'
    ACCEPTED = 'accepted'
    DECLINED = 'declined'
    CANCELLED = 'cancelled'
    REVOKED = 'revoked'


class RecordShareRequestRow(Base):
    """ORM-представление таблицы `record_share_requests`."""

    __tablename__ = 'record_share_requests'

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    from_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), index=True)
    to_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), index=True)
    status: Mapped[RecordShareStatusRow] = mapped_column(
        Enum(
            RecordShareStatusRow,
            name='record_share_status',
            native_enum=True,
            validate_strings=True,
            values_callable=_enum_values,
        ),
        default=RecordShareStatusRow.PENDING,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=moscow_now)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RecordShareRow(Base):
    """ORM-представление таблицы `record_shares`."""

    __tablename__ = 'record_shares'

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    request_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('record_share_requests.id'),
        index=True,
    )
    record_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('medical_records.id'), index=True)
    patient_passport_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('patient_passports.id'),
        nullable=True,
        index=True,
    )
    status: Mapped[RecordShareStatusRow] = mapped_column(
        Enum(
            RecordShareStatusRow,
            name='record_share_status',
            native_enum=True,
            validate_strings=True,
            values_callable=_enum_values,
        ),
        default=RecordShareStatusRow.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=moscow_now)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

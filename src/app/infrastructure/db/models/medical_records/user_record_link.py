"""ORM-модель фактического доступа пользователя к записи."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.auth.user import _enum_values


class UserRecordLinkSourceRow(StrEnum):
    """Источники появления доступа к записи."""

    CREATOR = 'creator'
    SHARE_ACCEPTED = 'share_accepted'
    IMPORTED = 'imported'
    MANUAL_ATTACH = 'manual_attach'


class UserRecordLinkRow(Base):
    """ORM-представление таблицы `user_record_links`."""

    __tablename__ = 'user_record_links'

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), index=True)
    record_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('medical_records.id'),
        index=True,
    )
    patient_passport_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('patient_passports.id'),
        nullable=True,
        index=True,
    )
    source: Mapped[UserRecordLinkSourceRow] = mapped_column(
        Enum(
            UserRecordLinkSourceRow,
            name='record_link_source',
            native_enum=True,
            validate_strings=True,
            values_callable=_enum_values,
        )
    )
    source_record_share_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('record_shares.id'),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

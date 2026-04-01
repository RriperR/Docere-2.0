"""ORM-модель вложений медицинской записи."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models._time import moscow_now
from app.infrastructure.db.models.auth.user import _enum_values


class FileAttachmentCategoryRow(StrEnum):
    """Категории ORM-модели вложений."""

    LAB = 'lab'
    IMAGING = 'imaging'
    DOCUMENT = 'document'
    OTHER = 'other'


class FileAttachmentRow(Base):
    """ORM-представление таблицы `file_attachments`."""

    __tablename__ = 'file_attachments'

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    record_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('medical_records.id'), index=True)
    uploaded_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), index=True)
    category: Mapped[FileAttachmentCategoryRow] = mapped_column(
        Enum(
            FileAttachmentCategoryRow,
            name='file_attachment_category',
            native_enum=True,
            validate_strings=True,
            values_callable=_enum_values,
        ),
        default=FileAttachmentCategoryRow.OTHER,
    )
    storage_key: Mapped[str] = mapped_column(String(length=512), unique=True)
    mime_type: Mapped[str] = mapped_column(String(length=255))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=moscow_now)

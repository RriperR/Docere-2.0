"""ORM-модель вложений медицинской записи."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, func, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.entities.file_attachment import FileAttachmentCategory
from app.infrastructure.db.base import Base
from app.infrastructure.db.models._enums import enum_values


class FileAttachmentRow(Base):
    """ORM-представление таблицы `file_attachments`."""

    __tablename__ = 'file_attachments'

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    record_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('medical_records.id'), index=True)
    comment_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('record_comments.id'),
        nullable=True,
        index=True,
    )
    uploaded_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), index=True)
    category: Mapped[FileAttachmentCategory] = mapped_column(
        Enum(
            FileAttachmentCategory,
            name='file_attachment_category',
            native_enum=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=FileAttachmentCategory.OTHER,
    )
    filename: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(length=512), unique=True)
    mime_type: Mapped[str] = mapped_column(String(length=255))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

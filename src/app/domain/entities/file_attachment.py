"""Доменные сущности вложений."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class FileAttachmentCategory(StrEnum):
    """Поддерживаемые категории вложений."""

    LAB = 'lab'
    IMAGING = 'imaging'
    DOCUMENT = 'document'
    OTHER = 'other'


@dataclass(frozen=True, slots=True)
class FileAttachment:
    """Вложение, связанное с медицинской записью."""

    id: UUID
    record_id: UUID
    comment_id: UUID | None
    uploaded_by_user_id: UUID
    uploaded_by_fio: str
    category: FileAttachmentCategory
    filename: str | None
    storage_key: str
    mime_type: str
    size_bytes: int
    uploaded_at: datetime

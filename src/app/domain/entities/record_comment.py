"""Доменные сущности комментариев к записям."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.file_attachment import FileAttachment


@dataclass(frozen=True, slots=True)
class RecordComment:
    """Append-only комментарий к медицинской записи."""

    id: UUID
    record_id: UUID
    author_user_id: UUID
    author_fio: str
    author_role: str
    body: str
    attachments: tuple[FileAttachment, ...]
    created_at: datetime

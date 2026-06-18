"""DTO сценариев вложений к медицинской записи."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AddRecordAttachmentDTO:
    """Входной DTO загрузки вложения к записи."""

    record_id: UUID
    actor_user_id: UUID
    filename: str
    content: bytes
    content_type: str

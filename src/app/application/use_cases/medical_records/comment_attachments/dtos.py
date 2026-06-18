"""DTO сценариев вложений к комментариям."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AddCommentAttachmentDTO:
    """Входной DTO загрузки вложения к комментарию."""

    record_id: UUID
    comment_id: UUID
    actor_user_id: UUID
    actor_role: str
    filename: str
    content: bytes
    content_type: str


@dataclass(frozen=True, slots=True)
class DownloadAttachmentDTO:
    """Входной DTO скачивания вложения."""

    attachment_id: UUID
    actor_user_id: UUID


@dataclass(frozen=True, slots=True)
class AttachmentContentDTO:
    """Содержимое вложения для отдачи клиенту."""

    filename: str
    mime_type: str
    content: bytes

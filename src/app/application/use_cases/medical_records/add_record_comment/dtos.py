"""DTO сценария создания комментария к медицинской записи."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AddRecordCommentDTO:
    """Входной DTO для добавления комментария к медицинской записи."""

    record_id: UUID
    actor_user_id: UUID
    actor_role: str
    actor_fio: str
    body: str

"""DTO порта репозитория событий аудита."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuditEventDTO:
    """Проекция события аудита для административного UI."""

    id: UUID
    actor_user_id: UUID | None
    actor_fio: str | None
    actor_email: str | None
    event_type: str
    entity_type: str
    entity_id: UUID
    metadata_json: dict[str, object]
    created_at: datetime

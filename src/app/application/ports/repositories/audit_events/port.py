"""Контракт репозитория событий аудита."""

from __future__ import annotations

from uuid import UUID

from app.application.ports.repositories.audit_events.dtos import AuditEventDTO


class AuditEventRepositoryPort:
    """Порт для записи и чтения событий аудита."""

    def record(
        self,
        *,
        actor_user_id: UUID | None,
        event_type: str,
        entity_type: str,
        entity_id: UUID,
        metadata_json: dict[str, object] | None = None,
    ) -> None:
        """Записать append-only событие аудита."""
        raise NotImplementedError

    def list_recent(self, *, limit: int) -> tuple[AuditEventDTO, ...]:
        """Вернуть последние события аудита."""
        raise NotImplementedError

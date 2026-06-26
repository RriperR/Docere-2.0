"""Контракт репозитория событий аудита."""

from __future__ import annotations

from app.application.ports.repositories.audit_events.dtos import AuditEventDTO


class AuditEventRepositoryPort:
    """Порт для чтения событий аудита."""

    def list_recent(self, *, limit: int) -> tuple[AuditEventDTO, ...]:
        """Вернуть последние события аудита."""
        raise NotImplementedError

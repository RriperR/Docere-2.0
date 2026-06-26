"""Сценарий просмотра событий аудита администратором."""

from __future__ import annotations

from app.application.ports.repositories.audit_events.dtos import AuditEventDTO
from app.application.ports.repositories.audit_events.port import AuditEventRepositoryPort


class AuditEventAccessDeniedError(Exception):
    """Текущий пользователь не может просматривать audit log."""


class ListAuditEventsUseCase:
    """Вернуть последние события audit log для администратора."""

    def __init__(self, repository: AuditEventRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий событий аудита.
        """
        self._repository = repository

    def execute(self, *, actor_role: str, limit: int = 50) -> tuple[AuditEventDTO, ...]:
        """Вернуть последние события аудита.

        Args:
            actor_role: Роль текущего пользователя.
            limit: Максимальное количество событий.

        Returns:
            Список событий аудита.

        Raises:
            AuditEventAccessDeniedError: Если текущий пользователь не администратор.
        """
        if actor_role != 'admin':
            raise AuditEventAccessDeniedError
        bounded_limit = max(1, min(limit, 200))
        return self._repository.list_recent(limit=bounded_limit)

"""Сценарий просмотра списка пользователей администратором."""

from __future__ import annotations

from app.application.ports.repositories.auth.port import AuthRepositoryPort
from app.application.use_cases.auth.common.dtos import AdminUserDTO


class ListUsersAccessDeniedError(Exception):
    """Текущий пользователь не может просматривать список пользователей."""


class ListUsersUseCase:
    """Вернуть список пользователей для администратора."""

    def __init__(self, repository: AuthRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий пользователей.
        """
        self._repository = repository

    def execute(self, *, actor_role: str, limit: int = 200) -> tuple[AdminUserDTO, ...]:
        """Вернуть список пользователей.

        Args:
            actor_role: Роль текущего пользователя.
            limit: Максимальное количество пользователей.

        Returns:
            Пользователи в административной проекции.

        Raises:
            ListUsersAccessDeniedError: Если текущий пользователь не администратор.
        """
        if actor_role != 'admin':
            raise ListUsersAccessDeniedError
        bounded_limit = max(1, min(limit, 500))
        return tuple(
            AdminUserDTO(
                id=user.id,
                fio=user.fio,
                email=user.email,
                phone=user.phone,
                date_of_birth=user.date_of_birth,
                role=user.role,
                status=user.status,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
            for user in self._repository.list_users(limit=bounded_limit)
        )

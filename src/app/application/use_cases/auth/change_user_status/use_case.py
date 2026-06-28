"""Сценарий блокировки и разблокировки пользователя администратором."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.ports.repositories.audit_events.port import AuditEventRepositoryPort
from app.application.ports.repositories.auth.dtos import AuthUserDTO
from app.application.ports.repositories.auth.port import AuthRepositoryPort
from app.application.use_cases.auth.common.dtos import AdminUserDTO


class ChangeUserStatusAccessDeniedError(Exception):
    """Текущий пользователь не может менять статусы учетных записей."""


class ChangeUserStatusNotFoundError(Exception):
    """Пользователь для изменения статуса не найден."""


class ChangeUserStatusValidationError(Exception):
    """Запрошен неподдерживаемый статус учетной записи."""


class ChangeUserStatusSelfBlockError(Exception):
    """Администратор попытался заблокировать собственную учетную запись."""


@dataclass(frozen=True, slots=True)
class ChangeUserStatusResultDTO:
    """Результат идемпотентного изменения статуса пользователя."""

    user: AdminUserDTO
    previous_status: str
    changed: bool


class ChangeUserStatusUseCase:
    """Изменить доступность учетной записи от имени администратора."""

    _allowed_statuses = frozenset({'active', 'blocked'})

    def __init__(self, repository: AuthRepositoryPort, audit_events: AuditEventRepositoryPort) -> None:
        """Инициализировать сценарий.

        Args:
            repository: Репозиторий пользователей.
            audit_events: Репозиторий событий аудита.
        """
        self._repository = repository
        self._audit_events = audit_events

    def execute(
        self,
        *,
        actor_user_id: UUID,
        actor_role: str,
        target_user_id: UUID,
        target_status: str,
    ) -> ChangeUserStatusResultDTO:
        """Установить статус пользователя и вернуть результат операции.

        Returns:
            Результат операции с обновленной проекцией пользователя.

        Raises:
            ChangeUserStatusAccessDeniedError: Если действие выполняет не администратор.
            ChangeUserStatusValidationError: Если передан неподдерживаемый статус.
            ChangeUserStatusNotFoundError: Если целевой пользователь не найден.
            ChangeUserStatusSelfBlockError: Если администратор блокирует себя.
        """
        if actor_role != 'admin':
            raise ChangeUserStatusAccessDeniedError
        if target_status not in self._allowed_statuses:
            raise ChangeUserStatusValidationError

        current_user = self._repository.find_by_id(user_id=target_user_id)
        if current_user is None:
            raise ChangeUserStatusNotFoundError
        if actor_user_id == target_user_id and target_status == 'blocked':
            raise ChangeUserStatusSelfBlockError

        if current_user.status == target_status:
            return ChangeUserStatusResultDTO(
                user=self._to_admin_user(current_user),
                previous_status=current_user.status,
                changed=False,
            )

        updated_user = self._repository.set_status(user_id=target_user_id, status=target_status)
        if updated_user is None:
            raise ChangeUserStatusNotFoundError
        result = ChangeUserStatusResultDTO(
            user=self._to_admin_user(updated_user),
            previous_status=current_user.status,
            changed=True,
        )
        self._audit_events.record(
            actor_user_id=actor_user_id,
            event_type='user_status_changed',
            entity_type='user',
            entity_id=target_user_id,
            metadata_json={
                'previous_status': result.previous_status,
                'status': result.user.status,
            },
        )
        return result

    @staticmethod
    def _to_admin_user(user: AuthUserDTO) -> AdminUserDTO:
        return AdminUserDTO(
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

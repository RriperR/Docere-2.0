"""Сценарий безопасной смены пароля пользователя."""

from __future__ import annotations

from uuid import UUID

from app.application.ports.repositories.audit_events.port import AuditEventRepositoryPort
from app.application.ports.repositories.auth.port import AuthRepositoryPort
from app.application.ports.security.password_hasher import PasswordHasherPort
from app.application.use_cases.auth.errors import (
    InvalidCurrentPasswordError,
    NewPasswordMatchesCurrentError,
    UserNotFoundError,
)


class ChangePasswordUseCase:
    """Проверить текущий пароль и сохранить новый хеш."""

    def __init__(
        self,
        repository: AuthRepositoryPort,
        password_hasher: PasswordHasherPort,
        audit_events: AuditEventRepositoryPort,
    ) -> None:
        """Инициализировать сценарий.

        Args:
            repository: Репозиторий пользователей.
            password_hasher: Сервис проверки и хеширования паролей.
            audit_events: Репозиторий событий аудита.
        """
        self._repository = repository
        self._password_hasher = password_hasher
        self._audit_events = audit_events

    def execute(self, *, user_id: UUID, current_password: str, new_password: str) -> None:
        """Сменить пароль пользователя.

        Args:
            user_id: Идентификатор текущего пользователя.
            current_password: Текущий пароль в открытом виде.
            new_password: Новый пароль в открытом виде.

        Raises:
            UserNotFoundError: Если пользователь не найден.
            InvalidCurrentPasswordError: Если текущий пароль неверен.
            NewPasswordMatchesCurrentError: Если новый пароль совпадает с текущим.
        """
        user = self._repository.find_by_id(user_id=user_id)
        if user is None:
            raise UserNotFoundError
        if not self._password_hasher.verify_password(
            plain_password=current_password,
            password_hash=user.password_hash,
        ):
            raise InvalidCurrentPasswordError
        if self._password_hasher.verify_password(
            plain_password=new_password,
            password_hash=user.password_hash,
        ):
            raise NewPasswordMatchesCurrentError

        password_hash = self._password_hasher.hash_password(plain_password=new_password)
        if not self._repository.set_password_hash(user_id=user_id, password_hash=password_hash):
            raise UserNotFoundError
        self._audit_events.record(
            actor_user_id=user_id,
            event_type='password_changed',
            entity_type='user',
            entity_id=user_id,
        )

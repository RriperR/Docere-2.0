"""Сценарии команд и запросов sharing-запросов."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.application.ports.repositories.share_requests.dtos import (
    CreateShareRequestResultDTO,
    ShareRequestDTO,
)
from app.application.ports.repositories.share_requests.port import ShareRequestRepositoryPort


class CreateShareRequestUseCase:
    """Создать sharing-запрос от текущего пользователя."""

    def __init__(self, repository: ShareRequestRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий sharing-запросов.
        """
        self._repository = repository

    def execute(
        self,
        *,
        from_user_id: UUID,
        to_user_email: str,
        record_ids: tuple[UUID, ...],
        message: str | None,
        expires_at: datetime | None,
    ) -> CreateShareRequestResultDTO:
        """Выполнить создание sharing-запроса.

        Args:
            from_user_id: Идентификатор отправителя.
            to_user_email: Email получателя.
            record_ids: Идентификаторы записей для sharing.
            message: Сообщение получателю.
            expires_at: Момент истечения доступа или ``None`` для бессрочного доступа.

        Returns:
            Созданный sharing-запрос и пропущенные записи.
        """
        return self._repository.create_share_request(
            from_user_id=from_user_id,
            to_user_email=to_user_email.strip().lower(),
            record_ids=tuple(dict.fromkeys(record_ids)),
            message=message.strip() if message else None,
            expires_at=expires_at,
        )


class ListInboxShareRequestsUseCase:
    """Вернуть входящие sharing-запросы пользователя."""

    def __init__(self, repository: ShareRequestRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий sharing-запросов.
        """
        self._repository = repository

    def execute(self, *, user_id: UUID) -> tuple[ShareRequestDTO, ...]:
        """Выполнить сценарий.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Входящие sharing-запросы.
        """
        return self._repository.list_inbox(user_id=user_id)


class ListOutboxShareRequestsUseCase:
    """Вернуть исходящие sharing-запросы пользователя."""

    def __init__(self, repository: ShareRequestRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий sharing-запросов.
        """
        self._repository = repository

    def execute(self, *, user_id: UUID) -> tuple[ShareRequestDTO, ...]:
        """Выполнить сценарий.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Исходящие sharing-запросы.
        """
        return self._repository.list_outbox(user_id=user_id)


class AcceptShareRequestUseCase:
    """Принять pending sharing-запрос."""

    def __init__(self, repository: ShareRequestRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий sharing-запросов.
        """
        self._repository = repository

    def execute(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Выполнить принятие запроса.

        Args:
            request_id: Идентификатор sharing-запроса.
            user_id: Идентификатор получателя.

        Returns:
            Обновленный sharing-запрос.
        """
        return self._repository.accept_request(request_id=request_id, user_id=user_id)


class DeclineShareRequestUseCase:
    """Отклонить pending sharing-запрос."""

    def __init__(self, repository: ShareRequestRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий sharing-запросов.
        """
        self._repository = repository

    def execute(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Выполнить отклонение запроса.

        Args:
            request_id: Идентификатор sharing-запроса.
            user_id: Идентификатор получателя.

        Returns:
            Обновленный sharing-запрос.
        """
        return self._repository.decline_request(request_id=request_id, user_id=user_id)


class CancelShareRequestUseCase:
    """Отменить pending sharing-запрос отправителем."""

    def __init__(self, repository: ShareRequestRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий sharing-запросов.
        """
        self._repository = repository

    def execute(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Выполнить отмену запроса.

        Args:
            request_id: Идентификатор sharing-запроса.
            user_id: Идентификатор отправителя.

        Returns:
            Обновленный sharing-запрос.
        """
        return self._repository.cancel_request(request_id=request_id, user_id=user_id)


class RevokeShareRequestUseCase:
    """Отозвать accepted sharing-запрос отправителем."""

    def __init__(self, repository: ShareRequestRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий sharing-запросов.
        """
        self._repository = repository

    def execute(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Выполнить отзыв запроса.

        Args:
            request_id: Идентификатор sharing-запроса.
            user_id: Идентификатор отправителя.

        Returns:
            Обновленный sharing-запрос.
        """
        return self._repository.revoke_request(request_id=request_id, user_id=user_id)

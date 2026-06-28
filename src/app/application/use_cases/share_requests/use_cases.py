"""Сценарии команд и запросов sharing-запросов."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.application.ports.repositories.audit_events.port import AuditEventRepositoryPort
from app.application.ports.repositories.share_requests.dtos import (
    CreateShareRequestResultDTO,
    ShareRequestDTO,
    ShareUserDTO,
)
from app.application.ports.repositories.share_requests.port import ShareRequestRepositoryPort


class CreateShareRequestUseCase:
    """Создать sharing-запрос от текущего пользователя."""

    def __init__(self, repository: ShareRequestRepositoryPort, audit_events: AuditEventRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий sharing-запросов.
            audit_events: Репозиторий событий аудита.
        """
        self._repository = repository
        self._audit_events = audit_events

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
        result = self._repository.create_share_request(
            from_user_id=from_user_id,
            to_user_email=to_user_email.strip().lower(),
            record_ids=tuple(dict.fromkeys(record_ids)),
            message=message.strip() if message else None,
            expires_at=expires_at,
        )
        if result.request is not None:
            self._audit_events.record(
                actor_user_id=from_user_id,
                event_type='share',
                entity_type='record_share_request',
                entity_id=result.request.id,
                metadata_json={
                    'record_ids': [str(record_id) for record_id in record_ids],
                    'expires_at': expires_at.isoformat() if expires_at else None,
                },
            )
        return result


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


class SearchShareRecipientsUseCase:
    """Найти доступных получателей sharing."""

    def __init__(self, repository: ShareRequestRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий sharing-запросов.
        """
        self._repository = repository

    def execute(self, *, user_id: UUID, query: str, limit: int = 10) -> tuple[ShareUserDTO, ...]:
        """Выполнить нормализованный поиск получателей.

        Returns:
            Не более десяти активных кандидатов.
        """
        normalized_query = query.strip().lower()
        if not normalized_query:
            return ()
        return self._repository.search_recipients(
            user_id=user_id,
            query=normalized_query,
            limit=max(1, min(limit, 10)),
        )


class AcceptShareRequestUseCase:
    """Принять pending sharing-запрос."""

    def __init__(self, repository: ShareRequestRepositoryPort, audit_events: AuditEventRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий sharing-запросов.
            audit_events: Репозиторий событий аудита.
        """
        self._repository = repository
        self._audit_events = audit_events

    def execute(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Выполнить принятие запроса.

        Args:
            request_id: Идентификатор sharing-запроса.
            user_id: Идентификатор получателя.

        Returns:
            Обновленный sharing-запрос.
        """
        request = self._repository.accept_request(request_id=request_id, user_id=user_id)
        self._record_audit(actor_user_id=user_id, event_type='accept', request_id=request.id)
        return request

    def _record_audit(self, *, actor_user_id: UUID, event_type: str, request_id: UUID) -> None:
        self._audit_events.record(
            actor_user_id=actor_user_id,
            event_type=event_type,
            entity_type='record_share_request',
            entity_id=request_id,
        )


class DeclineShareRequestUseCase(AcceptShareRequestUseCase):
    """Отклонить pending sharing-запрос."""

    def execute(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Выполнить отклонение запроса.

        Args:
            request_id: Идентификатор sharing-запроса.
            user_id: Идентификатор получателя.

        Returns:
            Обновленный sharing-запрос.
        """
        request = self._repository.decline_request(request_id=request_id, user_id=user_id)
        self._record_audit(actor_user_id=user_id, event_type='decline', request_id=request.id)
        return request


class CancelShareRequestUseCase(AcceptShareRequestUseCase):
    """Отменить pending sharing-запрос отправителем."""

    def execute(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Выполнить отмену запроса.

        Args:
            request_id: Идентификатор sharing-запроса.
            user_id: Идентификатор отправителя.

        Returns:
            Обновленный sharing-запрос.
        """
        request = self._repository.cancel_request(request_id=request_id, user_id=user_id)
        self._record_audit(actor_user_id=user_id, event_type='cancel', request_id=request.id)
        return request


class RevokeShareRequestUseCase(AcceptShareRequestUseCase):
    """Отозвать accepted sharing-запрос отправителем."""

    def execute(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Выполнить отзыв запроса.

        Args:
            request_id: Идентификатор sharing-запроса.
            user_id: Идентификатор отправителя.

        Returns:
            Обновленный sharing-запрос.
        """
        request = self._repository.revoke_request(request_id=request_id, user_id=user_id)
        self._record_audit(actor_user_id=user_id, event_type='revoke', request_id=request.id)
        return request

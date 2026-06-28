"""Контракт репозитория sharing-запросов."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.application.ports.repositories.share_requests.dtos import (
    CreateShareRequestResultDTO,
    ShareRequestDTO,
    ShareUserDTO,
)


class ShareRequestRepositoryPort:
    """Порт для команд и запросов sharing-запросов."""

    def create_share_request(
        self,
        *,
        from_user_id: UUID,
        to_user_email: str,
        record_ids: tuple[UUID, ...],
        message: str | None,
        expires_at: datetime | None,
    ) -> CreateShareRequestResultDTO:
        """Создать sharing-запрос.

        Returns:
            Созданный запрос и список пропущенных записей.
        """
        raise NotImplementedError

    def list_inbox(self, *, user_id: UUID) -> tuple[ShareRequestDTO, ...]:
        """Вернуть входящие sharing-запросы пользователя.

        Returns:
            Входящие запросы.
        """
        raise NotImplementedError

    def list_outbox(self, *, user_id: UUID) -> tuple[ShareRequestDTO, ...]:
        """Вернуть исходящие sharing-запросы пользователя.

        Returns:
            Исходящие запросы.
        """
        raise NotImplementedError

    def search_recipients(self, *, user_id: UUID, query: str, limit: int) -> tuple[ShareUserDTO, ...]:
        """Найти активных получателей sharing.

        Returns:
            Кандидаты без текущего пользователя.
        """
        raise NotImplementedError

    def accept_request(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Принять pending sharing-запрос.

        Returns:
            Обновленный запрос.
        """
        raise NotImplementedError

    def decline_request(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Отклонить pending sharing-запрос.

        Returns:
            Обновленный запрос.
        """
        raise NotImplementedError

    def cancel_request(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Отменить pending sharing-запрос отправителем.

        Returns:
            Обновленный запрос.
        """
        raise NotImplementedError

    def revoke_request(self, *, request_id: UUID, user_id: UUID) -> ShareRequestDTO:
        """Отозвать accepted sharing-запрос отправителем.

        Returns:
            Обновленный запрос.
        """
        raise NotImplementedError

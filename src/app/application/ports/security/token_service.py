"""Контракт сервиса выпуска и проверки токенов."""

from __future__ import annotations

from uuid import UUID


class TokenServicePort:
    """Порт работы с access- и refresh-токенами."""

    def create_access_token(self, user_id: UUID) -> str:
        """Сгенерировать access-токен для пользователя.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Сгенерированный токен.
        """
        raise NotImplementedError

    def create_refresh_token(self, user_id: UUID) -> str:
        """Сгенерировать refresh-токен для пользователя.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Сгенерированный refresh-токен.
        """
        raise NotImplementedError

    def decode_access_token(self, token: str) -> UUID:
        """Декодировать access-токен и вернуть идентификатор пользователя.

        Args:
            token: JWT access-токен.

        Returns:
            Идентификатор пользователя.

        Raises:
            ValueError: Если токен недействителен.
        """
        raise NotImplementedError

    def decode_refresh_token(self, token: str) -> UUID:
        """Декодировать refresh-токен и вернуть идентификатор пользователя.

        Args:
            token: JWT refresh-токен.

        Returns:
            Идентификатор пользователя.

        Raises:
            ValueError: Если токен недействителен.
        """
        raise NotImplementedError

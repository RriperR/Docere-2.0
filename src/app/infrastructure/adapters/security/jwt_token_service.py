"""JWT-реализация сервиса токенов."""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from enum import StrEnum
from uuid import UUID

import jwt
from jwt import InvalidTokenError as JwtInvalidTokenError

from app.application.ports.security.token_service import TokenServicePort


class TokenType(StrEnum):
    """Тип JWT-токена."""

    ACCESS = 'access'
    REFRESH = 'refresh'


class JwtTokenServiceAdapter(TokenServicePort):
    """Сервис выпуска и валидации JWT access- и refresh-токенов."""

    def __init__(
        self,
        secret_key: str,
        access_ttl_minutes: int,
        refresh_ttl_minutes: int,
        algorithm: str = 'HS256',
    ) -> None:
        """Инициализировать сервис токенов.

        Args:
            secret_key: Секрет подписи токена.
            access_ttl_minutes: Время жизни access-токена в минутах.
            refresh_ttl_minutes: Время жизни refresh-токена в минутах.
            algorithm: Алгоритм подписи JWT.
        """
        self._secret_key = secret_key
        self._access_ttl_minutes = access_ttl_minutes
        self._refresh_ttl_minutes = refresh_ttl_minutes
        self._algorithm = algorithm

    def create_access_token(self, user_id: UUID) -> str:
        """Создать access-токен.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            JWT токен в виде строки.
        """
        return self._create_token(user_id, self._access_ttl_minutes, TokenType.ACCESS)

    def create_refresh_token(self, user_id: UUID) -> str:
        """Создать refresh-токен.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            JWT refresh-токен в виде строки.
        """
        return self._create_token(user_id, self._refresh_ttl_minutes, TokenType.REFRESH)

    def decode_access_token(self, token: str) -> UUID:
        """Проверить и декодировать access-токен.

        Args:
            token: JWT токен.

        Returns:
            Идентификатор пользователя из токена.
        """
        return self._decode_token(token=token, expected_type=TokenType.ACCESS)

    def decode_refresh_token(self, token: str) -> UUID:
        """Проверить и декодировать refresh-токен.

        Args:
            token: JWT токен.

        Returns:
            Идентификатор пользователя из токена.
        """
        return self._decode_token(token=token, expected_type=TokenType.REFRESH)

    def _create_token(self, user_id: UUID, ttl_minutes: int, token_type: TokenType) -> str:
        """Сформировать JWT токен указанного типа.

        Args:
            user_id: Идентификатор пользователя.
            ttl_minutes: Время жизни токена.
            token_type: Тип токена (`access` или `refresh`).

        Returns:
            JWT токен.
        """
        now = datetime.now(tz=UTC)
        expires_at = now + timedelta(minutes=ttl_minutes)
        payload = {
            'sub': str(user_id),
            'iat': int(now.timestamp()),
            'exp': int(expires_at.timestamp()),
            'type': token_type,
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def _decode_token(self, token: str, expected_type: TokenType) -> UUID:
        """Декодировать JWT токен и проверить ожидаемый тип.

        Args:
            token: JWT токен.
            expected_type: Ожидаемый тип токена.

        Returns:
            Идентификатор пользователя из токена.

        Raises:
            ValueError: Если токен недействителен или имеет другой тип.
        """
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except JwtInvalidTokenError as exc:
            raise ValueError('Invalid token') from exc

        token_type = payload.get('type')
        if token_type != expected_type:
            raise ValueError('Invalid token type')

        subject = payload.get('sub')
        if not isinstance(subject, str):
            raise ValueError('Token subject is missing')

        try:
            return UUID(subject)
        except ValueError as exc:
            raise ValueError('Token subject is not a valid UUID') from exc

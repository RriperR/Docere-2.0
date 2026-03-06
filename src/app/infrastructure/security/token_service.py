"""JWT-реализация сервиса токенов."""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from uuid import UUID

import jwt
from jwt import InvalidTokenError as JwtInvalidTokenError

from app.application.ports.token_service import TokenServicePort


class JwtTokenService(TokenServicePort):
    """Сервис выпуска и валидации JWT access-токенов."""

    def __init__(self, secret_key: str, ttl_minutes: int, algorithm: str = 'HS256') -> None:
        """Инициализировать сервис токенов.

        Args:
            secret_key: Секрет подписи токена.
            ttl_minutes: Время жизни токена в минутах.
            algorithm: Алгоритм подписи JWT.
        """
        self._secret_key = secret_key
        self._ttl_minutes = ttl_minutes
        self._algorithm = algorithm

    def create_access_token(self, user_id: UUID) -> str:
        """Создать access-токен.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            JWT токен в виде строки.
        """
        now = datetime.now(tz=UTC)
        expires_at = now + timedelta(minutes=self._ttl_minutes)
        payload = {
            'sub': str(user_id),
            'iat': int(now.timestamp()),
            'exp': int(expires_at.timestamp()),
        }
        token: str = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return token

    def decode_access_token(self, token: str) -> UUID:
        """Проверить и декодировать access-токен.

        Args:
            token: JWT токен.

        Returns:
            Идентификатор пользователя из токена.

        Raises:
            ValueError: Если токен некорректен или не содержит валидный subject.
        """
        try:
            payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
        except JwtInvalidTokenError as exc:
            raise ValueError('Invalid token') from exc

        subject = payload.get('sub')
        if not isinstance(subject, str):
            raise ValueError('Token subject is missing')

        try:
            return UUID(subject)
        except ValueError as exc:
            raise ValueError('Token subject is not a valid UUID') from exc

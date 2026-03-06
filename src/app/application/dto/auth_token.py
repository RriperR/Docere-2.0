"""DTO токена аутентификации."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthToken:
    """Данные access-токена для ответа клиенту."""

    access_token: str
    token_type: str = 'bearer'  # noqa: S105

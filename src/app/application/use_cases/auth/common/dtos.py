"""Общие DTO сценариев аутентификации."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from uuid import UUID


class ResponseTokenType(StrEnum):
    """Тип токена в HTTP-ответе."""

    BEARER = 'bearer'


@dataclass(frozen=True, slots=True)
class AuthTokenDTO:
    """Данные access- и refresh-токенов для ответа клиенту."""

    access_token: str
    refresh_token: str
    token_type: ResponseTokenType = ResponseTokenType.BEARER


@dataclass(frozen=True, slots=True)
class AuthenticatedUserDTO:
    """Публичные поля пользователя для REST-ответа."""

    id: UUID
    fio: str
    email: str
    phone: str
    date_of_birth: date | None
    role: str
    status: str

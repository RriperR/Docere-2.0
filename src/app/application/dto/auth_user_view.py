"""DTO представления пользователя после аутентификации."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuthUserView:
    """Публичные поля пользователя для REST-ответа."""

    id: UUID
    fio: str
    email: str
    phone: str
    date_of_birth: date | None
    role: str
    status: str

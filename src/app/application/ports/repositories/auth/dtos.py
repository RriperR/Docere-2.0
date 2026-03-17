"""DTO контракта репозитория пользователей."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AuthUserDTO:
    """Снимок пользователя для application-слоя."""

    id: UUID
    fio: str
    email: str
    phone: str
    date_of_birth: date | None
    password_hash: str
    role: str
    status: str
    created_at: datetime
    updated_at: datetime

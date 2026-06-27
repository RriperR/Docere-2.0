"""DTO профиля пользователя."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True, slots=True)
class UserProfileDTO:
    """Согласованная проекция пользователя и его медицинского паспорта."""

    id: UUID
    fio: str
    email: str
    phone: str
    date_of_birth: date | None
    role: str
    status: str
    specialty: str | None

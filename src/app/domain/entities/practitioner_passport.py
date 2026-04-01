"""Доменные сущности паспортов врачей."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class PractitionerPassportStatus(StrEnum):
    """Поддерживаемые статусы паспорта врача."""

    DRAFT = 'draft'
    CONFIRMED = 'confirmed'


@dataclass(frozen=True, slots=True)
class PractitionerPassport:
    """Паспорт врача в доменной модели."""

    id: UUID
    created_by_user_id: UUID | None
    user_id: UUID | None
    full_name: str
    specialty: str | None
    organization: str | None
    position: str | None
    email: str | None
    phone: str | None
    status: PractitionerPassportStatus
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime

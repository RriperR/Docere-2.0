"""Доменные сущности паспортных данных пациента."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID


class PatientPassportStatus(StrEnum):
    """Статусы паспортной карточки пациента."""

    DRAFT = 'draft'
    CONFIRMED = 'confirmed'


@dataclass(frozen=True, slots=True)
class PatientPassport:
    """Паспортные данные пациента в доменной модели."""

    id: UUID
    created_by_user_id: UUID
    patient_user_id: UUID | None
    fio: str
    date_of_birth: date | None
    email: str | None
    phone: str | None
    status: PatientPassportStatus
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime

"""DTO порта репозитория sharing-запросов."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ShareUserDTO:
    """Краткая публичная проекция пользователя в sharing API."""

    id: UUID
    fio: str
    email: str
    role: str


@dataclass(frozen=True, slots=True)
class RecordShareDTO:
    """Проекция отдельной записи внутри sharing-запроса."""

    id: UUID
    record_id: UUID
    patient_passport_id: UUID | None
    status: str
    created_at: datetime
    responded_at: datetime | None
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class ShareRequestDTO:
    """Проекция request-level sharing-запроса."""

    id: UUID
    from_user: ShareUserDTO
    to_user: ShareUserDTO
    status: str
    message: str | None
    shares: tuple[RecordShareDTO, ...]
    created_at: datetime
    responded_at: datetime | None
    cancelled_at: datetime | None
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class CreateShareRequestResultDTO:
    """Результат создания sharing-запроса."""

    request: ShareRequestDTO | None
    skipped_record_ids: tuple[UUID, ...]

"""Доменные сущности медицинских записей."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID


class MedicalRecordStatus(StrEnum):
    """Поддерживаемые статусы медицинской записи."""

    UNCONFIRMED = 'unconfirmed'
    CONFIRMED = 'confirmed'


class MedicalRecordType(StrEnum):
    """Поддерживаемые типы медицинской записи."""

    CONSULTATION_RESULT = 'consultation_result'
    EXAM_RESULT = 'exam_result'
    LAB_RESULT = 'lab_result'
    OTHER = 'other'


@dataclass(frozen=True, slots=True)
class MedicalRecord:
    """Неизменяемая медицинская запись без пользовательского контекста доступа."""

    id: UUID
    creator_user_id: UUID
    author_practitioner_passport_id: UUID | None
    status: MedicalRecordStatus
    record_type: MedicalRecordType
    event_date: date
    title: str | None
    appointment_location: str | None
    clinical_summary: str | None
    payload_json: dict[str, object]
    confirmed_by_user_id: UUID | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime

"""Доменные сущности медицинских записей."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID


class MedicalRecordStatus(StrEnum):
    """Статусы медицинской записи."""

    DRAFT = 'draft'
    UNCONFIRMED = 'unconfirmed'
    CONFIRMED = 'confirmed'
    REJECTED = 'rejected'


class MedicalRecordType(StrEnum):
    """Поддерживаемые типы медицинской записи."""

    CONSULTATION_RESULT = 'consultation_result'
    EXAM_RESULT = 'exam_result'
    LAB_RESULT = 'lab_result'
    OTHER = 'other'


@dataclass(frozen=True, slots=True)
class MedicalRecord:
    """Медицинская запись без пользовательского контекста доступа."""

    id: UUID
    creator_user_id: UUID
    status: MedicalRecordStatus
    record_type: MedicalRecordType
    event_date: date
    title: str | None
    payload_json: dict[str, object]
    created_at: datetime
    updated_at: datetime

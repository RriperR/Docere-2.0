"""Общие DTO сценариев работы с медицинскими записями."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class MedicalRecordDTO:
    """Проекция медицинской записи в контексте конкретного пользователя."""

    id: UUID
    creator_user_id: UUID
    status: str
    record_type: str
    event_date: date
    title: str | None
    payload_json: dict[str, object]
    patient_passport_id: UUID | None
    created_at: datetime
    updated_at: datetime

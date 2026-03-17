"""DTO сценария создания медицинской записи."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CreateMedicalRecordDTO:
    """Входной DTO для создания медицинской записи."""

    actor_user_id: UUID
    actor_role: str
    patient_passport_id: UUID
    record_type: str
    event_date: date
    title: str | None
    payload_json: dict[str, object]

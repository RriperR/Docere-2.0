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
    actor_fio: str
    actor_email: str
    actor_phone: str
    patient_passport_id: UUID
    author_practitioner_passport_id: UUID | None
    author_practitioner_full_name: str | None
    author_practitioner_specialty: str | None
    author_practitioner_organization: str | None
    author_practitioner_position: str | None
    author_practitioner_email: str | None
    author_practitioner_phone: str | None
    record_type: str
    event_date: date
    title: str | None
    appointment_location: str | None
    clinical_summary: str | None
    payload_json: dict[str, object]

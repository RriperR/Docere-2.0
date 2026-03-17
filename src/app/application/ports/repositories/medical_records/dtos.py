"""DTO контракта репозитория медицинских записей."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.medical_record import MedicalRecord


@dataclass(frozen=True, slots=True)
class AccessibleMedicalRecordDTO:
    """Медицинская запись в контексте доступа конкретного пользователя."""

    record: MedicalRecord
    patient_passport_id: UUID | None

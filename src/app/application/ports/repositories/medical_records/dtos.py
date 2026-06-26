"""DTO контракта репозитория медицинских записей."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.domain.entities.file_attachment import FileAttachment
from app.domain.entities.medical_record import MedicalRecord
from app.domain.entities.practitioner_passport import PractitionerPassport
from app.domain.entities.record_comment import RecordComment


@dataclass(frozen=True, slots=True)
class AccessibleMedicalRecordDTO:
    """Медицинская запись в контексте доступа конкретного пользователя."""

    record: MedicalRecord
    patient_passport_id: UUID | None
    author_practitioner_passport: PractitionerPassport | None
    comments: tuple[RecordComment, ...]
    attachments: tuple[FileAttachment, ...]


@dataclass(frozen=True, slots=True)
class DuplicateMedicalRecordCandidateDTO:
    """Краткая запись, похожая на импортируемую группу."""

    record_id: UUID
    patient_passport_id: UUID
    title: str | None
    record_type: str
    event_date: date
    status: str
    match_reason: str

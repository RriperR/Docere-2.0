"""DTO контракта репозитория медицинских записей."""

from __future__ import annotations

from dataclasses import dataclass
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

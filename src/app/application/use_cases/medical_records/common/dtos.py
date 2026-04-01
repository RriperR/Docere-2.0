"""Общие DTO сценариев медицинских записей."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PractitionerPassportDTO:
    """Проекция паспорта врача для API-ответов."""

    id: UUID
    user_id: UUID | None
    full_name: str
    specialty: str | None
    organization: str | None
    position: str | None
    email: str | None
    phone: str | None
    status: str


@dataclass(frozen=True, slots=True)
class RecordCommentDTO:
    """Проекция комментария к записи."""

    id: UUID
    record_id: UUID
    author_user_id: UUID
    body: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class FileAttachmentDTO:
    """Проекция вложения."""

    id: UUID
    record_id: UUID
    uploaded_by_user_id: UUID
    category: str
    storage_key: str
    mime_type: str
    size_bytes: int
    uploaded_at: datetime


@dataclass(frozen=True, slots=True)
class MedicalRecordDTO:
    """Проекция медицинской записи в пользовательском контексте доступа."""

    id: UUID
    creator_user_id: UUID
    author_practitioner_passport_id: UUID | None
    status: str
    record_type: str
    event_date: date
    title: str | None
    appointment_location: str | None
    clinical_summary: str | None
    payload_json: dict[str, object]
    patient_passport_id: UUID | None
    author_practitioner_passport: PractitionerPassportDTO | None
    comments: tuple[RecordCommentDTO, ...]
    attachments: tuple[FileAttachmentDTO, ...]
    comments_count: int
    attachments_count: int
    created_at: datetime
    updated_at: datetime

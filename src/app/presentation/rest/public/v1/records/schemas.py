"""Pydantic-схемы REST-эндпоинтов медицинских записей."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.presentation.rest.serialization import MoscowDatetime


class CreateMedicalRecordRequestSchema(BaseModel):
    """Тело запроса на создание медицинской записи."""

    patient_passport_id: UUID
    author_practitioner_passport_id: UUID | None = None
    author_practitioner_full_name: str | None = Field(default=None, max_length=255)
    author_practitioner_specialty: str | None = Field(default=None, max_length=255)
    author_practitioner_organization: str | None = Field(default=None, max_length=255)
    author_practitioner_position: str | None = Field(default=None, max_length=255)
    author_practitioner_email: str | None = Field(default=None, max_length=320)
    author_practitioner_phone: str | None = Field(default=None, max_length=32)
    record_type: str = Field(pattern='^(consultation_result|exam_result|lab_result|other)$')
    event_date: date
    title: str | None = Field(default=None, max_length=255)
    appointment_location: str | None = Field(default=None, max_length=255)
    clinical_summary: str | None = None
    payload_json: dict[str, object]


class CreateRecordCommentRequestSchema(BaseModel):
    """Тело запроса на добавление комментария к записи."""

    body: str = Field(min_length=1, max_length=4000)


class PractitionerPassportResponseSchema(BaseModel):
    """Схема ответа для паспорта врача."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None
    full_name: str
    specialty: str | None
    organization: str | None
    position: str | None
    email: str | None
    phone: str | None
    status: str


class FileAttachmentResponseSchema(BaseModel):
    """Схема ответа для вложения записи."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    record_id: UUID
    comment_id: UUID | None
    uploaded_by_user_id: UUID
    uploaded_by_fio: str
    category: str
    filename: str | None
    storage_key: str
    mime_type: str
    size_bytes: int
    uploaded_at: MoscowDatetime


class RecordCommentResponseSchema(BaseModel):
    """Схема ответа для комментария к записи."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    record_id: UUID
    author_user_id: UUID
    author_fio: str
    author_role: str
    body: str
    attachments: tuple[FileAttachmentResponseSchema, ...]
    created_at: MoscowDatetime


class MedicalRecordResponseSchema(BaseModel):
    """Схема ответа для detail медицинской записи."""

    model_config = ConfigDict(from_attributes=True)

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
    author_practitioner_passport: PractitionerPassportResponseSchema | None
    comments: tuple[RecordCommentResponseSchema, ...]
    attachments: tuple[FileAttachmentResponseSchema, ...]
    comments_count: int
    attachments_count: int
    created_at: MoscowDatetime
    updated_at: MoscowDatetime

"""Pydantic-схемы REST-эндпоинтов архивов."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.presentation.rest.serialization import MoscowDatetime


class ImportJobResponseSchema(BaseModel):
    """Схема ответа ImportJob."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    uploaded_by_user_id: UUID
    status: str
    original_filename: str | None
    archive_storage_key: str | None
    size_bytes: int | None
    report_json: dict[str, object]
    created_at: MoscowDatetime
    finished_at: MoscowDatetime | None


class ImportRecordGroupResolveSchema(BaseModel):
    """Решение пользователя по группе файлов импортируемой записи."""

    group_id: str
    action: str = Field(pattern='^(create|skip)$')
    record_type: str | None = Field(default=None, pattern='^(consultation_result|exam_result|lab_result|other)$')
    event_date: date | None = None
    title: str | None = Field(default=None, max_length=255)


class ImportPatientResolveSchema(BaseModel):
    """Решение пользователя по кандидату пациента из ImportJob."""

    candidate_id: str
    action: str = Field(pattern='^(existing|create|skip)$')
    patient_passport_id: UUID | None = None
    fio: str | None = Field(default=None, max_length=255)
    date_of_birth: date | None = None
    record_groups: list[ImportRecordGroupResolveSchema] = Field(default_factory=list)


class ResolveImportJobRequestSchema(BaseModel):
    """Тело запроса финализации ImportJob после review."""

    decisions: list[ImportPatientResolveSchema] = Field(min_length=1)

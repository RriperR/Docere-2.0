"""Pydantic-схемы для REST-эндпоинтов медицинских записей."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateMedicalRecordRequestSchema(BaseModel):
    """Тело запроса на создание медицинской записи."""

    patient_passport_id: UUID
    record_type: str = Field(
        pattern='^(consultation_result|exam_result|lab_result|other)$',
    )
    event_date: date
    title: str | None = Field(default=None, max_length=255)
    payload_json: dict[str, object]


class MedicalRecordResponseSchema(BaseModel):
    """Схема ответа с медицинской записью."""

    model_config = ConfigDict(from_attributes=True)

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

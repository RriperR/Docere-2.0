"""Pydantic-схемы REST-эндпоинтов пациентов."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.presentation.rest.public.v1.records.schemas import PractitionerPassportResponseSchema
from app.presentation.rest.serialization import MoscowDatetime


class CreatePatientRequestSchema(BaseModel):
    """Тело запроса на создание паспорта пациента сотрудником."""

    fio: str = Field(min_length=1, max_length=255)
    date_of_birth: date | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)


class PatientSummaryResponseSchema(BaseModel):
    """Краткая схема пациента для списка и детальной карточки."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fio: str
    date_of_birth: date | None
    email: str | None
    phone: str | None
    status: str
    access_context: str
    record_count: int
    last_record_date: date | None


class PatientSearchResultResponseSchema(BaseModel):
    """Результат fuzzy-поиска PatientPassport."""

    model_config = ConfigDict(from_attributes=True)

    patient: PatientSummaryResponseSchema
    match_score: float


class PatientRecordSummaryResponseSchema(BaseModel):
    """Краткая схема медицинской записи внутри карточки пациента."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    record_type: str
    event_date: date
    title: str | None
    appointment_location: str | None
    clinical_summary: str | None
    author_practitioner_passport: PractitionerPassportResponseSchema | None
    comments_count: int
    attachments_count: int
    created_at: MoscowDatetime
    updated_at: MoscowDatetime

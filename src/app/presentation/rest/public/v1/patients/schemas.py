"""Pydantic-схемы REST-эндпоинтов пациентов."""

from __future__ import annotations

from datetime import date
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator
from pydantic_core import PydanticCustomError

from app.domain.entities.medical_record import MedicalRecordStatus, MedicalRecordType
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
    confirmed_by_user_id: UUID | None
    confirmed_at: MoscowDatetime | None
    creator_user_id: UUID
    creator_fio: str
    author_practitioner_passport: PractitionerPassportResponseSchema | None
    comments_count: int
    attachments_count: int
    created_at: MoscowDatetime
    updated_at: MoscowDatetime


class PatientPageQuerySchema(BaseModel):
    """Проверенные параметры серверной страницы пациентов."""

    model_config = ConfigDict(extra='forbid')

    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)
    q: str | None = Field(
        default=None, max_length=255, description='Буквальный поиск; маскировать в gateway/APM логах.'
    )


class PatientRecordPageQuerySchema(PatientPageQuerySchema):
    """Проверенные фильтры истории с включительным интервалом дат."""

    record_type: MedicalRecordType | None = None
    confirmation_status: MedicalRecordStatus | None = None
    event_date_from: date | None = None
    event_date_to: date | None = None

    @model_validator(mode='after')
    def validate_date_interval(self) -> Self:
        """Отклонить обратный интервал дат события.

        Returns:
            Проверенные параметры истории.

        Raises:
            PydanticCustomError: Если начало интервала позже конца.
        """
        if (
            self.event_date_from is not None
            and self.event_date_to is not None
            and self.event_date_from > self.event_date_to
        ):
            raise PydanticCustomError('date_interval', 'event_date_from must not be after event_date_to')
        return self


class PatientPageResponseSchema(BaseModel):
    """Страница пациентов с прежней схемой элемента."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PatientSummaryResponseSchema]
    total: int
    offset: int
    limit: int


class PatientRecordPageResponseSchema(BaseModel):
    """Страница истории с прежней схемой элемента."""

    model_config = ConfigDict(from_attributes=True)

    items: list[PatientRecordSummaryResponseSchema]
    total: int
    offset: int
    limit: int

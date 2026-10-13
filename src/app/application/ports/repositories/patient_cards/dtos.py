"""DTO порта репозитория карточек пациентов."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.application.use_cases.medical_records.common.dtos import PractitionerPassportDTO
from app.domain.entities.medical_record import MedicalRecordStatus, MedicalRecordType


@dataclass(frozen=True, slots=True)
class PatientSummaryDTO:
    """Краткое представление доступной карточки пациента."""

    id: UUID
    fio: str
    date_of_birth: date | None
    email: str | None
    phone: str | None
    status: str
    access_context: str
    record_count: int
    last_record_date: date | None


@dataclass(frozen=True, slots=True)
class PatientSearchResultDTO:
    """Кандидат PatientPassport при fuzzy-поиске."""

    patient: PatientSummaryDTO
    match_score: float


@dataclass(frozen=True, slots=True)
class PatientRecordSummaryDTO:
    """Краткое представление записи внутри карточки пациента."""

    id: UUID
    status: str
    record_type: str
    event_date: date
    title: str | None
    appointment_location: str | None
    clinical_summary: str | None
    confirmed_by_user_id: UUID | None
    confirmed_at: datetime | None
    creator_user_id: UUID
    creator_fio: str
    author_practitioner_passport: PractitionerPassportDTO | None
    comments_count: int
    attachments_count: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PatientPageFilterDTO:
    """Параметры серверной страницы пациентов и буквального поиска ФИО."""

    offset: int = 0
    limit: int = 20
    q: str | None = None


@dataclass(frozen=True, slots=True)
class PatientRecordPageFilterDTO(PatientPageFilterDTO):
    """Фильтры доступной истории пациента без поиска комментариев и текста PDF."""

    record_type: MedicalRecordType | None = None
    confirmation_status: MedicalRecordStatus | None = None
    event_date_from: date | None = None
    event_date_to: date | None = None


@dataclass(frozen=True, slots=True)
class PatientPageDTO:
    """Страница доступных пациентов с общим числом совпадений."""

    items: tuple[PatientSummaryDTO, ...]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True, slots=True)
class PatientRecordPageDTO:
    """Страница доступных записей с общим числом совпадений."""

    items: tuple[PatientRecordSummaryDTO, ...]
    total: int
    offset: int
    limit: int

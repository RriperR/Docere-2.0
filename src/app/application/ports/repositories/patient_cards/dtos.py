"""DTO порта репозитория карточек пациентов."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.application.use_cases.medical_records.common.dtos import PractitionerPassportDTO


@dataclass(frozen=True, slots=True)
class PatientSummaryDTO:
    """Краткое представление доступной карточки пациента."""

    id: UUID
    fio: str
    date_of_birth: date | None
    email: str | None
    phone: str | None
    status: str
    record_count: int
    last_record_date: date | None


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
    author_practitioner_passport: PractitionerPassportDTO | None
    comments_count: int
    attachments_count: int
    created_at: datetime
    updated_at: datetime

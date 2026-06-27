"""DTO порта заявок на роль врача."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DoctorRoleReviewerCandidateDTO:
    """Пользователь, которого пациент может выбрать проверяющим."""

    id: UUID
    fio: str
    email: str
    role: str
    specialty: str | None


@dataclass(frozen=True, slots=True)
class DoctorRoleReviewDTO:
    """Публичная проекция решения проверяющего."""

    id: UUID
    reviewer_user_id: UUID
    reviewer_fio: str
    reviewer_email: str
    reviewer_role: str
    reviewer_specialty: str | None
    status: str
    note: str | None
    created_at: datetime
    responded_at: datetime | None


@dataclass(frozen=True, slots=True)
class DoctorRoleApplicationDTO:
    """Публичная проекция заявки на роль врача."""

    id: UUID
    applicant_user_id: UUID
    applicant_fio: str
    applicant_email: str
    applicant_date_of_birth: date | None
    specialty: str
    status: str
    reviews: tuple[DoctorRoleReviewDTO, ...]
    created_at: datetime
    resolved_at: datetime | None

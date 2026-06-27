"""Pydantic-схемы заявок на роль врача."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DoctorRoleReviewerCandidateSchema(BaseModel):
    """Доступный пациенту проверяющий."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fio: str
    email: EmailStr
    role: Literal['doctor', 'admin']
    specialty: str | None


class CreateDoctorRoleApplicationSchema(BaseModel):
    """Тело запроса создания заявки."""

    specialty: str = Field(min_length=2, max_length=255)
    reviewer_user_ids: list[UUID] = Field(min_length=1, max_length=10)


class ReviewDoctorRoleApplicationSchema(BaseModel):
    """Решение выбранного проверяющего."""

    decision: Literal['approved', 'rejected']
    note: str | None = Field(default=None, max_length=2000)


class DoctorRoleReviewResponseSchema(BaseModel):
    """Решение одного проверяющего."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reviewer_user_id: UUID
    reviewer_fio: str
    reviewer_email: EmailStr
    reviewer_role: str
    reviewer_specialty: str | None
    status: str
    note: str | None
    created_at: datetime
    responded_at: datetime | None


class DoctorRoleApplicationResponseSchema(BaseModel):
    """Заявка на роль врача с прогрессом проверок."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    applicant_user_id: UUID
    applicant_fio: str
    applicant_email: EmailStr
    applicant_date_of_birth: date | None
    specialty: str
    status: str
    reviews: list[DoctorRoleReviewResponseSchema]
    created_at: datetime
    resolved_at: datetime | None

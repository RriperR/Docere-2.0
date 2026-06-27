"""Доменная модель заявки пациента на роль врача."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class DoctorRoleApplicationStatus(StrEnum):
    """Статусы заявки на роль врача."""

    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'


class DoctorRoleReviewStatus(StrEnum):
    """Статусы решения выбранного проверяющего."""

    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'


@dataclass(frozen=True, slots=True)
class DoctorRoleReview:
    """Решение проверяющего по заявке пациента."""

    id: UUID
    application_id: UUID
    reviewer_user_id: UUID
    reviewer_role: str
    reviewer_specialty: str | None
    status: DoctorRoleReviewStatus
    note: str | None
    created_at: datetime
    responded_at: datetime | None


@dataclass(frozen=True, slots=True)
class DoctorRoleApplication:
    """Заявка пациента на получение роли врача."""

    id: UUID
    applicant_user_id: UUID
    specialty: str
    status: DoctorRoleApplicationStatus
    reviews: tuple[DoctorRoleReview, ...]
    created_at: datetime
    resolved_at: datetime | None


def evaluate_doctor_role_application(application: DoctorRoleApplication) -> DoctorRoleApplicationStatus:
    """Вычислить итог заявки по решениям выбранных проверяющих.

    Администратор одобряет заявку единолично. Без администратора нужны
    одобрения двух разных врачей заявленной специализации.

    Returns:
        Новый статус заявки.
    """
    if application.status != DoctorRoleApplicationStatus.PENDING:
        return application.status

    reviews = application.reviews
    if any(
        review.reviewer_role == 'admin' and review.status == DoctorRoleReviewStatus.APPROVED
        for review in reviews
    ):
        return DoctorRoleApplicationStatus.APPROVED

    normalized_specialty = application.specialty.casefold()
    doctor_reviews = tuple(
        review
        for review in reviews
        if review.reviewer_role == 'doctor'
        and (review.reviewer_specialty or '').casefold() == normalized_specialty
    )
    doctor_approvals = sum(review.status == DoctorRoleReviewStatus.APPROVED for review in doctor_reviews)
    if doctor_approvals >= 2:
        return DoctorRoleApplicationStatus.APPROVED

    admin_pending = any(
        review.reviewer_role == 'admin' and review.status == DoctorRoleReviewStatus.PENDING
        for review in reviews
    )
    doctor_pending = sum(review.status == DoctorRoleReviewStatus.PENDING for review in doctor_reviews)
    if not admin_pending and doctor_approvals + doctor_pending < 2:
        return DoctorRoleApplicationStatus.REJECTED
    return DoctorRoleApplicationStatus.PENDING

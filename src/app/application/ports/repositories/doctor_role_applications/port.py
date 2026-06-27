"""Контракт репозитория заявок на роль врача."""

from __future__ import annotations

from uuid import UUID

from app.application.ports.repositories.doctor_role_applications.dtos import (
    DoctorRoleApplicationDTO,
    DoctorRoleReviewerCandidateDTO,
)


class DoctorRoleApplicationRepositoryPort:
    """Порт команд и запросов workflow роли врача."""

    def list_specialties(self) -> tuple[str, ...]:
        """Вернуть специализации активных подтвержденных врачей."""
        raise NotImplementedError

    def list_eligible_reviewers(
        self,
        *,
        specialty: str,
        excluded_user_id: UUID,
    ) -> tuple[DoctorRoleReviewerCandidateDTO, ...]:
        """Вернуть администраторов и врачей нужной специализации."""
        raise NotImplementedError

    def get_pending_by_applicant(self, *, applicant_user_id: UUID) -> DoctorRoleApplicationDTO | None:
        """Вернуть активную заявку пациента, если она существует."""
        raise NotImplementedError

    def create_application(
        self,
        *,
        applicant_user_id: UUID,
        specialty: str,
        reviewers: tuple[DoctorRoleReviewerCandidateDTO, ...],
    ) -> DoctorRoleApplicationDTO:
        """Создать заявку и pending-решения выбранных проверяющих."""
        raise NotImplementedError

    def list_by_applicant(self, *, applicant_user_id: UUID) -> tuple[DoctorRoleApplicationDTO, ...]:
        """Вернуть историю заявок пользователя."""
        raise NotImplementedError

    def list_inbox(self, *, reviewer_user_id: UUID) -> tuple[DoctorRoleApplicationDTO, ...]:
        """Вернуть pending-заявки выбранного проверяющего."""
        raise NotImplementedError

    def get_for_review(
        self,
        *,
        application_id: UUID,
        reviewer_user_id: UUID,
    ) -> DoctorRoleApplicationDTO | None:
        """Заблокировать и вернуть заявку, назначенную проверяющему."""
        raise NotImplementedError

    def record_review(
        self,
        *,
        application_id: UUID,
        reviewer_user_id: UUID,
        decision: str,
        note: str | None,
    ) -> DoctorRoleApplicationDTO | None:
        """Сохранить решение проверяющего и вернуть заявку."""
        raise NotImplementedError

    def finalize_application(
        self,
        *,
        application_id: UUID,
        status: str,
    ) -> DoctorRoleApplicationDTO | None:
        """Завершить заявку и при одобрении выдать роль врача."""
        raise NotImplementedError

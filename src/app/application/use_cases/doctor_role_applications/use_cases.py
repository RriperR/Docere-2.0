"""Сценарии подачи и проверки заявки на роль врача."""

from __future__ import annotations

from uuid import UUID

from app.application.ports.repositories.audit_events.port import AuditEventRepositoryPort
from app.application.ports.repositories.doctor_role_applications.dtos import (
    DoctorRoleApplicationDTO,
    DoctorRoleReviewerCandidateDTO,
)
from app.application.ports.repositories.doctor_role_applications.port import DoctorRoleApplicationRepositoryPort
from app.application.use_cases.doctor_role_applications.errors import (
    DoctorRoleApplicationAccessDeniedError,
    DoctorRoleApplicationConflictError,
    DoctorRoleApplicationNotFoundError,
    DoctorRoleApplicationValidationError,
)
from app.domain.entities.doctor_role_application import (
    DoctorRoleApplication,
    DoctorRoleApplicationStatus,
    DoctorRoleReview,
    DoctorRoleReviewStatus,
    evaluate_doctor_role_application,
)


class ListDoctorSpecialtiesUseCase:
    """Вернуть пациенту специализации доступных проверяющих."""

    def __init__(self, repository: DoctorRoleApplicationRepositoryPort) -> None:
        """Инициализировать сценарий.

        Args:
            repository: Репозиторий заявок на роль врача.
        """
        self._repository = repository

    def execute(self, *, actor_role: str) -> tuple[str, ...]:
        """Вернуть специализации.

        Returns:
            Доступные специализации врачей.
        """
        _ensure_patient(actor_role)
        return self._repository.list_specialties()


class ListDoctorRoleReviewersUseCase:
    """Вернуть пациенту проверяющих для выбранной специализации."""

    def __init__(self, repository: DoctorRoleApplicationRepositoryPort) -> None:
        """Инициализировать сценарий.

        Args:
            repository: Репозиторий заявок на роль врача.
        """
        self._repository = repository

    def execute(
        self,
        *,
        actor_user_id: UUID,
        actor_role: str,
        specialty: str,
    ) -> tuple[DoctorRoleReviewerCandidateDTO, ...]:
        """Вернуть подходящих врачей и администраторов.

        Returns:
            Подходящие врачи и администраторы.
        """
        _ensure_patient(actor_role)
        normalized_specialty = _normalize_specialty(specialty)
        return self._repository.list_eligible_reviewers(
            specialty=normalized_specialty,
            excluded_user_id=actor_user_id,
        )


class CreateDoctorRoleApplicationUseCase:
    """Создать заявку пациента с выбранными проверяющими."""

    def __init__(
        self,
        repository: DoctorRoleApplicationRepositoryPort,
        audit_events: AuditEventRepositoryPort,
    ) -> None:
        """Инициализировать сценарий.

        Args:
            repository: Репозиторий заявок на роль врача.
            audit_events: Репозиторий событий аудита.
        """
        self._repository = repository
        self._audit_events = audit_events

    def execute(
        self,
        *,
        actor_user_id: UUID,
        actor_role: str,
        specialty: str,
        reviewer_user_ids: tuple[UUID, ...],
    ) -> DoctorRoleApplicationDTO:
        """Создать новую заявку.

        Returns:
            Созданная заявка с назначенными проверяющими.

        Raises:
            DoctorRoleApplicationConflictError: Если уже есть pending-заявка.
            DoctorRoleApplicationValidationError: Если набор проверяющих не может дать кворум.
        """
        _ensure_patient(actor_role)
        normalized_specialty = _normalize_specialty(specialty)
        unique_reviewer_ids = tuple(dict.fromkeys(reviewer_user_ids))
        if not unique_reviewer_ids or len(unique_reviewer_ids) > 10:
            raise DoctorRoleApplicationValidationError
        if self._repository.get_pending_by_applicant(applicant_user_id=actor_user_id) is not None:
            raise DoctorRoleApplicationConflictError

        eligible = self._repository.list_eligible_reviewers(
            specialty=normalized_specialty,
            excluded_user_id=actor_user_id,
        )
        eligible_by_id = {candidate.id: candidate for candidate in eligible}
        try:
            selected = tuple(eligible_by_id[reviewer_id] for reviewer_id in unique_reviewer_ids)
        except KeyError as exc:
            raise DoctorRoleApplicationValidationError from exc

        admin_count = sum(candidate.role == 'admin' for candidate in selected)
        doctor_count = sum(
            candidate.role == 'doctor' and (candidate.specialty or '').casefold() == normalized_specialty.casefold()
            for candidate in selected
        )
        if admin_count < 1 and doctor_count < 2:
            raise DoctorRoleApplicationValidationError
        application = self._repository.create_application(
            applicant_user_id=actor_user_id,
            specialty=normalized_specialty,
            reviewers=selected,
        )
        self._audit_events.record(
            actor_user_id=actor_user_id,
            event_type='doctor_role_application_created',
            entity_type='doctor_role_application',
            entity_id=application.id,
            metadata_json={
                'specialty': application.specialty,
                'reviewer_user_ids': [str(value) for value in unique_reviewer_ids],
            },
        )
        return application


class ListDoctorRoleApplicationsUseCase:
    """Вернуть пользователю историю его заявок."""

    def __init__(self, repository: DoctorRoleApplicationRepositoryPort) -> None:
        """Инициализировать сценарий.

        Args:
            repository: Репозиторий заявок на роль врача.
        """
        self._repository = repository

    def execute(self, *, actor_user_id: UUID) -> tuple[DoctorRoleApplicationDTO, ...]:
        """Вернуть историю заявок текущего пользователя.

        Returns:
            Заявки пользователя от новых к старым.
        """
        return self._repository.list_by_applicant(applicant_user_id=actor_user_id)


class ListDoctorRoleApplicationInboxUseCase:
    """Вернуть врачу или администратору назначенные заявки."""

    def __init__(self, repository: DoctorRoleApplicationRepositoryPort) -> None:
        """Инициализировать сценарий.

        Args:
            repository: Репозиторий заявок на роль врача.
        """
        self._repository = repository

    def execute(self, *, actor_user_id: UUID, actor_role: str) -> tuple[DoctorRoleApplicationDTO, ...]:
        """Вернуть входящие заявки.

        Returns:
            Pending-заявки, назначенные текущему проверяющему.

        Raises:
            DoctorRoleApplicationAccessDeniedError: Если пользователь не врач и не администратор.
        """
        if actor_role not in {'doctor', 'admin'}:
            raise DoctorRoleApplicationAccessDeniedError
        return self._repository.list_inbox(reviewer_user_id=actor_user_id)


class ReviewDoctorRoleApplicationUseCase:
    """Сохранить решение проверяющего и пересчитать кворум."""

    def __init__(
        self,
        repository: DoctorRoleApplicationRepositoryPort,
        audit_events: AuditEventRepositoryPort,
    ) -> None:
        """Инициализировать сценарий.

        Args:
            repository: Репозиторий заявок на роль врача.
            audit_events: Репозиторий событий аудита.
        """
        self._repository = repository
        self._audit_events = audit_events

    def execute(
        self,
        *,
        application_id: UUID,
        actor_user_id: UUID,
        actor_role: str,
        decision: str,
        note: str | None,
    ) -> DoctorRoleApplicationDTO:
        """Одобрить или отклонить назначенную заявку.

        Returns:
            Заявка с обновленным решением и итоговым статусом.

        Raises:
            DoctorRoleApplicationAccessDeniedError: Если пользователь не может проверять заявки.
            DoctorRoleApplicationNotFoundError: Если заявка не назначена пользователю.
            DoctorRoleApplicationConflictError: Если заявка или решение уже финальны.
            DoctorRoleApplicationValidationError: Если решение неизвестно.
        """
        if actor_role not in {'doctor', 'admin'}:
            raise DoctorRoleApplicationAccessDeniedError
        if decision not in {'approved', 'rejected'}:
            raise DoctorRoleApplicationValidationError
        application = self._repository.get_for_review(
            application_id=application_id,
            reviewer_user_id=actor_user_id,
        )
        if application is None:
            raise DoctorRoleApplicationNotFoundError
        if application.status != 'pending':
            raise DoctorRoleApplicationConflictError
        own_review = next(
            (review for review in application.reviews if review.reviewer_user_id == actor_user_id),
            None,
        )
        if own_review is None or own_review.reviewer_role != actor_role:
            raise DoctorRoleApplicationAccessDeniedError
        if own_review.status != 'pending':
            raise DoctorRoleApplicationConflictError

        updated = self._repository.record_review(
            application_id=application_id,
            reviewer_user_id=actor_user_id,
            decision=decision,
            note=note.strip() if note and note.strip() else None,
        )
        if updated is None:
            raise DoctorRoleApplicationNotFoundError
        target_status = evaluate_doctor_role_application(_to_domain(updated))
        if target_status != DoctorRoleApplicationStatus.PENDING:
            finalized = self._repository.finalize_application(
                application_id=application_id,
                status=target_status.value,
            )
            if finalized is None:
                raise DoctorRoleApplicationNotFoundError
            result = finalized
        else:
            result = updated
        self._audit_events.record(
            actor_user_id=actor_user_id,
            event_type='doctor_role_application_reviewed',
            entity_type='doctor_role_application',
            entity_id=result.id,
            metadata_json={
                'decision': decision,
                'application_status': result.status,
                'specialty': result.specialty,
            },
        )
        return result


def _ensure_patient(actor_role: str) -> None:
    if actor_role != 'patient':
        raise DoctorRoleApplicationAccessDeniedError


def _normalize_specialty(value: str) -> str:
    normalized = ' '.join(value.split())
    if len(normalized) < 2 or len(normalized) > 255:
        raise DoctorRoleApplicationValidationError
    return normalized


def _to_domain(application: DoctorRoleApplicationDTO) -> DoctorRoleApplication:
    return DoctorRoleApplication(
        id=application.id,
        applicant_user_id=application.applicant_user_id,
        specialty=application.specialty,
        status=DoctorRoleApplicationStatus(application.status),
        reviews=tuple(
            DoctorRoleReview(
                id=review.id,
                application_id=application.id,
                reviewer_user_id=review.reviewer_user_id,
                reviewer_role=review.reviewer_role,
                reviewer_specialty=review.reviewer_specialty,
                status=DoctorRoleReviewStatus(review.status),
                note=review.note,
                created_at=review.created_at,
                responded_at=review.responded_at,
            )
            for review in application.reviews
        ),
        created_at=application.created_at,
        resolved_at=application.resolved_at,
    )

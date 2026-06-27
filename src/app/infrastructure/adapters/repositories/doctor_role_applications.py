"""SQLAlchemy-адаптер заявок на роль врача."""

from __future__ import annotations

from datetime import datetime, UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ports.repositories.doctor_role_applications.dtos import (
    DoctorRoleApplicationDTO,
    DoctorRoleReviewDTO,
    DoctorRoleReviewerCandidateDTO,
)
from app.application.ports.repositories.doctor_role_applications.port import DoctorRoleApplicationRepositoryPort
from app.domain.entities.doctor_role_application import (
    DoctorRoleApplicationStatus,
    DoctorRoleReviewStatus,
)
from app.domain.entities.practitioner_passport import PractitionerPassportStatus
from app.infrastructure.db.models.auth.doctor_role_application import (
    DoctorRoleApplicationRow,
    DoctorRoleReviewRow,
)
from app.infrastructure.db.models.auth.user import UserRole, UserRow, UserStatus
from app.infrastructure.db.models.medical_records.practitioner_passport import PractitionerPassportRow


class SqlAlchemyDoctorRoleApplicationRepositoryAdapter(DoctorRoleApplicationRepositoryPort):
    """Хранить заявки, решения и повышение роли в одной транзакции."""

    def __init__(self, session: Session) -> None:
        """Инициализировать адаптер.

        Args:
            session: Активная SQLAlchemy-сессия.
        """
        self._session = session

    def list_specialties(self) -> tuple[str, ...]:
        """Вернуть специализации активных подтвержденных врачей.

        Returns:
            Отсортированные уникальные специализации.
        """
        values = self._session.scalars(
            select(PractitionerPassportRow.specialty)
            .join(UserRow, UserRow.id == PractitionerPassportRow.user_id)
            .where(
                UserRow.role == UserRole.DOCTOR,
                UserRow.status == UserStatus.ACTIVE,
                PractitionerPassportRow.status == PractitionerPassportStatus.CONFIRMED,
                PractitionerPassportRow.specialty.is_not(None),
            )
            .distinct()
            .order_by(PractitionerPassportRow.specialty.asc()),
        ).all()
        return tuple(value for value in values if value and value.strip())

    def list_eligible_reviewers(
        self,
        *,
        specialty: str,
        excluded_user_id: UUID,
    ) -> tuple[DoctorRoleReviewerCandidateDTO, ...]:
        """Вернуть активных администраторов и врачей нужной специализации.

        Returns:
            Проверяющие, которых пациент может выбрать.
        """
        admins = self._session.scalars(
            select(UserRow)
            .where(
                UserRow.id != excluded_user_id,
                UserRow.role == UserRole.ADMIN,
                UserRow.status == UserStatus.ACTIVE,
            )
            .order_by(UserRow.fio.asc()),
        ).all()
        doctor_rows = self._session.execute(
            select(UserRow, PractitionerPassportRow.specialty)
            .join(PractitionerPassportRow, PractitionerPassportRow.user_id == UserRow.id)
            .where(
                UserRow.id != excluded_user_id,
                UserRow.role == UserRole.DOCTOR,
                UserRow.status == UserStatus.ACTIVE,
                PractitionerPassportRow.status == PractitionerPassportStatus.CONFIRMED,
                PractitionerPassportRow.specialty.is_not(None),
            )
            .order_by(UserRow.fio.asc()),
        ).all()

        candidates = [
            DoctorRoleReviewerCandidateDTO(
                id=user.id,
                fio=user.fio,
                email=user.email,
                role='admin',
                specialty=None,
            )
            for user in admins
        ]
        seen_ids = {candidate.id for candidate in candidates}
        for user, doctor_specialty in doctor_rows:
            if user.id in seen_ids or not doctor_specialty or doctor_specialty.casefold() != specialty.casefold():
                continue
            candidates.append(
                DoctorRoleReviewerCandidateDTO(
                    id=user.id,
                    fio=user.fio,
                    email=user.email,
                    role='doctor',
                    specialty=doctor_specialty,
                ),
            )
            seen_ids.add(user.id)
        return tuple(candidates)

    def get_pending_by_applicant(self, *, applicant_user_id: UUID) -> DoctorRoleApplicationDTO | None:
        """Вернуть pending-заявку пациента.

        Returns:
            Активная заявка или ``None``.
        """
        row = self._session.scalar(
            select(DoctorRoleApplicationRow).where(
                DoctorRoleApplicationRow.applicant_user_id == applicant_user_id,
                DoctorRoleApplicationRow.status == DoctorRoleApplicationStatus.PENDING,
            ),
        )
        return self._to_dto(row) if row is not None else None

    def create_application(
        self,
        *,
        applicant_user_id: UUID,
        specialty: str,
        reviewers: tuple[DoctorRoleReviewerCandidateDTO, ...],
    ) -> DoctorRoleApplicationDTO:
        """Создать заявку и решения выбранных проверяющих.

        Returns:
            Созданная заявка.
        """
        application = DoctorRoleApplicationRow(
            applicant_user_id=applicant_user_id,
            specialty=specialty,
            status=DoctorRoleApplicationStatus.PENDING,
        )
        self._session.add(application)
        self._session.flush()
        self._session.add_all(
            [
                DoctorRoleReviewRow(
                    application_id=application.id,
                    reviewer_user_id=reviewer.id,
                    reviewer_role=reviewer.role,
                    reviewer_specialty=reviewer.specialty,
                    status=DoctorRoleReviewStatus.PENDING,
                )
                for reviewer in reviewers
            ],
        )
        self._session.flush()
        return self._to_dto(application)

    def list_by_applicant(self, *, applicant_user_id: UUID) -> tuple[DoctorRoleApplicationDTO, ...]:
        """Вернуть историю заявок пользователя.

        Returns:
            Заявки пользователя от новых к старым.
        """
        rows = self._session.scalars(
            select(DoctorRoleApplicationRow)
            .where(DoctorRoleApplicationRow.applicant_user_id == applicant_user_id)
            .order_by(DoctorRoleApplicationRow.created_at.desc(), DoctorRoleApplicationRow.id.desc()),
        ).all()
        return tuple(self._to_dto(row) for row in rows)

    def list_inbox(self, *, reviewer_user_id: UUID) -> tuple[DoctorRoleApplicationDTO, ...]:
        """Вернуть pending-заявки выбранного проверяющего.

        Returns:
            Назначенные проверяющему заявки.
        """
        rows = self._session.scalars(
            select(DoctorRoleApplicationRow)
            .join(DoctorRoleReviewRow, DoctorRoleReviewRow.application_id == DoctorRoleApplicationRow.id)
            .where(
                DoctorRoleReviewRow.reviewer_user_id == reviewer_user_id,
                DoctorRoleReviewRow.status == DoctorRoleReviewStatus.PENDING,
                DoctorRoleApplicationRow.status == DoctorRoleApplicationStatus.PENDING,
            )
            .order_by(DoctorRoleApplicationRow.created_at.asc()),
        ).all()
        return tuple(self._to_dto(row) for row in rows)

    def get_for_review(
        self,
        *,
        application_id: UUID,
        reviewer_user_id: UUID,
    ) -> DoctorRoleApplicationDTO | None:
        """Заблокировать и вернуть назначенную проверяющему заявку.

        Returns:
            Назначенная заявка или ``None``.
        """
        row = self._session.scalar(
            select(DoctorRoleApplicationRow)
            .join(DoctorRoleReviewRow, DoctorRoleReviewRow.application_id == DoctorRoleApplicationRow.id)
            .where(
                DoctorRoleApplicationRow.id == application_id,
                DoctorRoleReviewRow.reviewer_user_id == reviewer_user_id,
            )
            .with_for_update(),
        )
        return self._to_dto(row) if row is not None else None

    def record_review(
        self,
        *,
        application_id: UUID,
        reviewer_user_id: UUID,
        decision: str,
        note: str | None,
    ) -> DoctorRoleApplicationDTO | None:
        """Сохранить решение проверяющего.

        Returns:
            Обновленная заявка или ``None``.
        """
        review = self._session.scalar(
            select(DoctorRoleReviewRow).where(
                DoctorRoleReviewRow.application_id == application_id,
                DoctorRoleReviewRow.reviewer_user_id == reviewer_user_id,
                DoctorRoleReviewRow.status == DoctorRoleReviewStatus.PENDING,
            ),
        )
        if review is None:
            return None
        review.status = DoctorRoleReviewStatus(decision)
        review.note = note
        review.responded_at = datetime.now(UTC)
        self._session.flush()
        application = self._session.get(DoctorRoleApplicationRow, application_id)
        return self._to_dto(application) if application is not None else None

    def finalize_application(
        self,
        *,
        application_id: UUID,
        status: str,
    ) -> DoctorRoleApplicationDTO | None:
        """Завершить заявку и при одобрении выдать роль врача.

        Returns:
            Завершенная заявка или ``None``.
        """
        application = self._session.get(DoctorRoleApplicationRow, application_id)
        if application is None or application.status != DoctorRoleApplicationStatus.PENDING:
            return None
        application.status = DoctorRoleApplicationStatus(status)
        application.resolved_at = datetime.now(UTC)
        if application.status == DoctorRoleApplicationStatus.APPROVED:
            self._promote_applicant(application)
        self._session.flush()
        return self._to_dto(application)

    def _promote_applicant(self, application: DoctorRoleApplicationRow) -> None:
        applicant = self._session.get(UserRow, application.applicant_user_id)
        if applicant is None:
            return
        applicant.role = UserRole.DOCTOR
        passport = self._session.scalar(
            select(PractitionerPassportRow).where(PractitionerPassportRow.user_id == applicant.id),
        )
        if passport is None:
            passport = PractitionerPassportRow(
                created_by_user_id=applicant.id,
                user_id=applicant.id,
                full_name=applicant.fio,
                specialty=application.specialty,
                email=applicant.email,
                phone=applicant.phone,
            )
            self._session.add(passport)
        passport.specialty = application.specialty
        passport.status = PractitionerPassportStatus.CONFIRMED
        passport.confirmed_at = datetime.now(UTC)

    def _to_dto(self, application: DoctorRoleApplicationRow) -> DoctorRoleApplicationDTO:
        applicant = self._session.get(UserRow, application.applicant_user_id)
        if applicant is None:
            raise RuntimeError('Doctor role application applicant does not exist')
        review_rows = self._session.scalars(
            select(DoctorRoleReviewRow)
            .where(DoctorRoleReviewRow.application_id == application.id)
            .order_by(DoctorRoleReviewRow.created_at.asc(), DoctorRoleReviewRow.id.asc()),
        ).all()
        reviews = []
        for review in review_rows:
            reviewer = self._session.get(UserRow, review.reviewer_user_id)
            if reviewer is None:
                continue
            reviews.append(
                DoctorRoleReviewDTO(
                    id=review.id,
                    reviewer_user_id=review.reviewer_user_id,
                    reviewer_fio=reviewer.fio,
                    reviewer_email=reviewer.email,
                    reviewer_role=review.reviewer_role,
                    reviewer_specialty=review.reviewer_specialty,
                    status=str(review.status),
                    note=review.note,
                    created_at=review.created_at,
                    responded_at=review.responded_at,
                ),
            )
        return DoctorRoleApplicationDTO(
            id=application.id,
            applicant_user_id=application.applicant_user_id,
            applicant_fio=applicant.fio,
            applicant_email=applicant.email,
            applicant_date_of_birth=applicant.date_of_birth,
            specialty=application.specialty,
            status=str(application.status),
            reviews=tuple(reviews),
            created_at=application.created_at,
            resolved_at=application.resolved_at,
        )

"""SQLAlchemy-адаптер согласованного профиля пользователя."""

from __future__ import annotations

from datetime import date, datetime, UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ports.repositories.user_profiles.dtos import UserProfileDTO
from app.application.ports.repositories.user_profiles.port import UserProfileRepositoryPort
from app.domain.entities.practitioner_passport import PractitionerPassportStatus
from app.infrastructure.db.models.auth.user import UserRole, UserRow
from app.infrastructure.db.models.medical_records.patient_passport import PatientPassportRow
from app.infrastructure.db.models.medical_records.practitioner_passport import PractitionerPassportRow


class SqlAlchemyUserProfileRepositoryAdapter(UserProfileRepositoryPort):
    """Обновить user и принадлежащие ему паспорта в одной сессии."""

    def __init__(self, session: Session) -> None:
        """Инициализировать адаптер.

        Args:
            session: Транзакционная SQLAlchemy-сессия.
        """
        self._session = session

    def get_profile(self, *, user_id: UUID) -> UserProfileDTO | None:
        """Вернуть профиль пользователя или ``None``.

        Returns:
            Согласованный профиль пользователя.
        """
        user = self._session.get(UserRow, user_id)
        if user is None:
            return None
        practitioner = self._get_practitioner(user_id)
        return self._to_dto(user, practitioner)

    def update_profile(
        self,
        *,
        user_id: UUID,
        fio: str,
        phone: str,
        date_of_birth: date | None,
        specialty: str | None,
    ) -> UserProfileDTO | None:
        """Обновить user и связанные медицинские паспорта.

        Returns:
            Обновлённый согласованный профиль.
        """
        user = self._session.get(UserRow, user_id)
        if user is None:
            return None
        user.fio = fio
        user.phone = phone
        user.date_of_birth = date_of_birth

        patient_passports = self._session.scalars(
            select(PatientPassportRow).where(PatientPassportRow.patient_user_id == user_id),
        ).all()
        for passport in patient_passports:
            passport.fio = fio
            passport.date_of_birth = date_of_birth
            passport.email = user.email
            passport.phone = phone

        practitioner = self._get_practitioner(user_id)
        if user.role == UserRole.DOCTOR:
            if practitioner is None:
                practitioner = PractitionerPassportRow(
                    created_by_user_id=user_id,
                    user_id=user_id,
                    full_name=fio,
                    specialty=specialty,
                    email=user.email,
                    phone=phone,
                    status=PractitionerPassportStatus.CONFIRMED,
                    confirmed_at=datetime.now(UTC),
                )
                self._session.add(practitioner)
            else:
                practitioner.full_name = fio
                practitioner.specialty = specialty
                practitioner.email = user.email
                practitioner.phone = phone
        self._session.flush()
        return self._to_dto(user, practitioner)

    def _get_practitioner(self, user_id: UUID) -> PractitionerPassportRow | None:
        return self._session.scalar(
            select(PractitionerPassportRow).where(PractitionerPassportRow.user_id == user_id),
        )

    @staticmethod
    def _to_dto(user: UserRow, practitioner: PractitionerPassportRow | None) -> UserProfileDTO:
        return UserProfileDTO(
            id=user.id,
            fio=user.fio,
            email=user.email,
            phone=user.phone,
            date_of_birth=user.date_of_birth,
            role=str(user.role),
            status=str(user.status),
            specialty=practitioner.specialty if practitioner is not None else None,
        )

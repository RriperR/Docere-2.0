"""SQLAlchemy-реализация репозитория паспортов пациентов."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.application.ports.repositories.patient_passports.port import PatientPassportRepositoryPort
from app.domain.entities.patient_passport import PatientPassportStatus
from app.infrastructure.db.models.medical_records.patient_passport import PatientPassportRow


class SqlAlchemyPatientPassportRepositoryAdapter(PatientPassportRepositoryPort):
    """Репозиторий для создания паспортов пациентов."""

    def __init__(self, session: Session) -> None:
        """Инициализировать репозиторий.

        Args:
            session: Активная SQLAlchemy-сессия.
        """
        self._session = session

    def create_confirmed_passport(
        self,
        *,
        user_id: UUID,
        fio: str,
        date_of_birth: date | None,
        email: str,
        phone: str,
        confirmed_at: datetime,
    ) -> None:
        """Создать подтвержденный паспорт пациента для пользователя.

        Args:
            user_id: Идентификатор пользователя-пациента.
            fio: ФИО пациента.
            date_of_birth: Дата рождения пациента.
            email: Email пациента.
            phone: Телефон пациента.
            confirmed_at: Время подтверждения паспорта.
        """
        patient_passport_row = PatientPassportRow(
            created_by_user_id=user_id,
            patient_user_id=user_id,
            fio=fio,
            date_of_birth=date_of_birth,
            email=email,
            phone=phone,
            status=PatientPassportStatus.CONFIRMED,
            confirmed_at=confirmed_at,
        )
        self._session.add(patient_passport_row)

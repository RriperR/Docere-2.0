"""Сценарий создания карточки пациента сотрудником."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.application.ports.repositories.patient_cards.dtos import PatientSummaryDTO
from app.application.ports.repositories.patient_cards.port import PatientCardRepositoryPort
from app.application.use_cases.patients.errors import PatientCardAccessDeniedError


class CreatePatientUseCase:
    """Создать черновой паспорт пациента от имени врача или администратора."""

    def __init__(self, repository: PatientCardRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий карточек пациентов.
        """
        self._repository = repository

    def execute(
        self,
        *,
        actor_user_id: UUID,
        actor_role: str,
        fio: str,
        date_of_birth: date | None,
        email: str | None,
        phone: str | None,
    ) -> PatientSummaryDTO:
        """Выполнить создание карточки пациента.

        Args:
            actor_user_id: Идентификатор текущего пользователя.
            actor_role: Роль текущего пользователя.
            fio: ФИО пациента.
            date_of_birth: Дата рождения, если указана.
            email: Email пациента, если указан.
            phone: Телефон пациента, если указан.

        Returns:
            Созданная карточка пациента.

        Raises:
            PatientCardAccessDeniedError: Если роль не может создавать карточки.
        """
        if actor_role not in {'doctor', 'admin'}:
            raise PatientCardAccessDeniedError

        return self._repository.create_patient_passport(
            created_by_user_id=actor_user_id,
            fio=fio.strip(),
            date_of_birth=date_of_birth,
            email=email.strip().lower() if email is not None else None,
            phone=phone,
        )

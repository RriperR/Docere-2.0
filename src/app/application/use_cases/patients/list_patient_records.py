"""Сценарий получения записей карточки пациента."""

from __future__ import annotations

from uuid import UUID

from app.application.ports.repositories.patient_cards.dtos import PatientRecordSummaryDTO
from app.application.ports.repositories.patient_cards.port import PatientCardRepositoryPort
from app.application.use_cases.patients.errors import PatientCardNotFoundError


class ListPatientRecordsUseCase:
    """Вернуть записи доступной карточки пациента."""

    def __init__(self, repository: PatientCardRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий карточек пациентов.
        """
        self._repository = repository

    def execute(self, *, patient_id: UUID, user_id: UUID, user_role: str) -> tuple[PatientRecordSummaryDTO, ...]:
        """Выполнить сценарий.

        Args:
            patient_id: Идентификатор карточки пациента.
            user_id: Идентификатор текущего пользователя.
            user_role: Роль текущего пользователя.

        Returns:
            Записи карточки пациента.

        Raises:
            PatientCardNotFoundError: Если карточка не найдена или недоступна.
        """
        patient = self._repository.get_accessible_patient(
            patient_id=patient_id,
            user_id=user_id,
            user_role=user_role,
        )
        if patient is None:
            raise PatientCardNotFoundError
        return self._repository.list_patient_records(patient_id=patient_id, user_id=user_id, user_role=user_role)

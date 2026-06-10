"""Сценарий получения доступных карточек пациентов."""

from __future__ import annotations

from uuid import UUID

from app.application.ports.repositories.patient_cards.dtos import PatientSummaryDTO
from app.application.ports.repositories.patient_cards.port import PatientCardRepositoryPort


class ListPatientsUseCase:
    """Вернуть карточки пациентов, доступные текущему пользователю."""

    def __init__(self, repository: PatientCardRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий карточек пациентов.
        """
        self._repository = repository

    def execute(self, *, user_id: UUID, user_role: str) -> tuple[PatientSummaryDTO, ...]:
        """Выполнить сценарий.

        Args:
            user_id: Идентификатор текущего пользователя.
            user_role: Роль текущего пользователя.

        Returns:
            Доступные карточки пациентов.
        """
        return self._repository.list_accessible_patients(user_id=user_id, user_role=user_role)

"""Сценарий fuzzy-поиска паспортов пациентов."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.application.ports.repositories.patient_cards.dtos import PatientSearchResultDTO
from app.application.ports.repositories.patient_cards.port import PatientCardRepositoryPort
from app.application.use_cases.patients.errors import PatientCardAccessDeniedError


class SearchPatientsUseCase:
    """Найти вероятные совпадения PatientPassport перед созданием нового паспорта."""

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
        query: str,
        date_of_birth: date | None,
        limit: int,
    ) -> tuple[PatientSearchResultDTO, ...]:
        """Выполнить fuzzy-поиск пациентов.

        Args:
            actor_user_id: Идентификатор текущего пользователя.
            actor_role: Роль текущего пользователя.
            query: Поисковая строка по ФИО, email или телефону.
            date_of_birth: Дата рождения для повышения точности, если указана.
            limit: Максимальное число результатов.

        Returns:
            Кандидаты PatientPassport с оценкой похожести.

        Raises:
            PatientCardAccessDeniedError: Если роль не может искать паспорта.
        """
        if actor_role not in {'doctor', 'admin'}:
            raise PatientCardAccessDeniedError

        normalized_query = query.strip()
        if not normalized_query:
            return ()

        return self._repository.search_patient_passports(
            query=normalized_query,
            date_of_birth=date_of_birth,
            requested_by_user_id=actor_user_id,
            requested_by_role=actor_role,
            limit=limit,
        )

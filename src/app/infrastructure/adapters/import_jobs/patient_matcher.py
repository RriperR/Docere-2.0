"""Адаптер поиска похожих пациентов для импорта."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.application.ports.import_jobs.patient_matcher import PatientMatcherPort
from app.application.ports.repositories.patient_cards.port import PatientCardRepositoryPort
from app.application.use_cases.import_jobs.dtos import PatientMatchCandidate


class NoopPatientMatcher(PatientMatcherPort):
    """Заглушка поиска пациентов."""

    def find_matches(
        self,
        *,
        fio: str,
        date_of_birth: date | None,
        requested_by_user_id: UUID | None,
        requested_by_role: str | None,
        limit: int = 5,
    ) -> tuple[PatientMatchCandidate, ...]:
        """Всегда вернуть пустой список.

        Returns:
            Пустой набор совпадений.
        """
        return ()


class RepositoryPatientMatcher(PatientMatcherPort):
    """Ищет похожих пациентов через репозиторий."""

    def __init__(self, repository: PatientCardRepositoryPort) -> None:
        """Инициализировать адаптер репозиторием."""
        self._repository = repository

    def find_matches(
        self,
        *,
        fio: str,
        date_of_birth: date | None,
        requested_by_user_id: UUID | None,
        requested_by_role: str | None,
        limit: int = 5,
    ) -> tuple[PatientMatchCandidate, ...]:
        """Вернуть похожих пациентов.

        Returns:
            Найденные совпадения пациентов.
        """
        if requested_by_user_id is None or requested_by_role is None:
            return ()
        matches = self._repository.search_patient_passports(
            query=fio,
            date_of_birth=date_of_birth,
            requested_by_user_id=requested_by_user_id,
            requested_by_role=requested_by_role,
            limit=limit,
        )
        return tuple(
            PatientMatchCandidate(
                id=str(match.patient.id),
                fio=match.patient.fio,
                date_of_birth=match.patient.date_of_birth,
                status=match.patient.status,
                match_score=match.match_score,
                match_type=_match_type(fio, date_of_birth, match.patient.fio, match.patient.date_of_birth),
            )
            for match in matches
        )


def _match_type(
    fio: str,
    date_of_birth: date | None,
    matched_fio: str,
    matched_date_of_birth: date | None,
) -> str:
    if (
        fio.casefold() == matched_fio.casefold()
        and date_of_birth is not None
        and date_of_birth == matched_date_of_birth
    ):
        return 'exact'
    return 'fuzzy'

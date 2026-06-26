"""Порт поиска существующих пациентов для черновика импорта."""

from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from app.application.use_cases.import_jobs.dtos import PatientMatchCandidate


class PatientMatcherPort(Protocol):
    """Абстракция поиска похожих существующих пациентов."""

    def find_matches(
        self,
        *,
        fio: str,
        date_of_birth: date | None,
        requested_by_user_id: UUID | None,
        requested_by_role: str | None,
        limit: int = 5,
    ) -> tuple[PatientMatchCandidate, ...]:
        """Вернуть похожих пациентов."""

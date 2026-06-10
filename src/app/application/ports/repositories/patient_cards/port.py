"""Контракт репозитория карточек пациентов."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.application.ports.repositories.patient_cards.dtos import (
    PatientRecordSummaryDTO,
    PatientSummaryDTO,
)


class PatientCardRepositoryPort:
    """Порт для чтения и создания динамических карточек пациентов."""

    def list_accessible_patients(self, *, user_id: UUID, user_role: str) -> tuple[PatientSummaryDTO, ...]:
        """Вернуть карточки пациентов, доступные пользователю.

        Returns:
            Список кратких представлений карточек.
        """
        raise NotImplementedError

    def create_patient_passport(
        self,
        *,
        created_by_user_id: UUID,
        fio: str,
        date_of_birth: date | None,
        email: str | None,
        phone: str | None,
    ) -> PatientSummaryDTO:
        """Создать черновой паспорт пациента сотрудником.

        Returns:
            Краткое представление созданной карточки.
        """
        raise NotImplementedError

    def get_accessible_patient(
        self,
        *,
        patient_id: UUID,
        user_id: UUID,
        user_role: str,
    ) -> PatientSummaryDTO | None:
        """Вернуть карточку пациента, если она доступна пользователю.

        Returns:
            Краткое представление карточки или ``None``.
        """
        raise NotImplementedError

    def list_patient_records(
        self,
        *,
        patient_id: UUID,
        user_id: UUID,
        user_role: str,
    ) -> tuple[PatientRecordSummaryDTO, ...]:
        """Вернуть записи доступной карточки пациента.

        Returns:
            Список кратких представлений записей.
        """
        raise NotImplementedError

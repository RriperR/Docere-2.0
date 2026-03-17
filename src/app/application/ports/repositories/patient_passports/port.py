"""Контракт репозитория паспортов пациентов."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID


class PatientPassportRepositoryPort:
    """Порт репозитория паспортов пациентов."""

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
        raise NotImplementedError

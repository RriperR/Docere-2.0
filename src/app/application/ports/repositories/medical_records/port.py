"""Контракт репозитория медицинских записей."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.application.ports.repositories.medical_records.dtos import AccessibleMedicalRecordDTO
from app.domain.entities.patient_passport import PatientPassport


class MedicalRecordRepositoryPort:
    """Порт для чтения и создания медицинских записей."""

    def get_patient_passport(self, patient_passport_id: UUID) -> PatientPassport | None:
        """Получить паспорт пациента по идентификатору.

        Args:
            patient_passport_id: Идентификатор паспортной карточки.

        Returns:
            Паспорт пациента или `None`, если он не найден.
        """
        raise NotImplementedError

    def create_record(
        self,
        creator_user_id: UUID,
        patient_passport_id: UUID,
        record_type: str,
        event_date: date,
        title: str | None,
        payload_json: dict[str, object],
    ) -> AccessibleMedicalRecordDTO:
        """Создать медицинскую запись и связать ее с автором.

        Args:
            creator_user_id: Идентификатор автора записи.
            patient_passport_id: Паспортная карточка, через которую автор видит запись.
            record_type: Тип записи.
            event_date: Дата медицинского события.
            title: Заголовок записи.
            payload_json: Медицинское содержимое записи.

        Returns:
            Созданная запись в пользовательском контексте автора.
        """
        raise NotImplementedError

    def get_accessible_record(
        self,
        record_id: UUID,
        user_id: UUID,
    ) -> AccessibleMedicalRecordDTO | None:
        """Получить запись, если она доступна пользователю.

        Args:
            record_id: Идентификатор записи.
            user_id: Идентификатор пользователя.

        Returns:
            Запись в пользовательском контексте или `None`, если доступа нет.
        """
        raise NotImplementedError

    def record_exists(self, record_id: UUID) -> bool:
        """Проверить существование медицинской записи.

        Args:
            record_id: Идентификатор записи.

        Returns:
            `True`, если запись существует, иначе `False`.
        """
        raise NotImplementedError

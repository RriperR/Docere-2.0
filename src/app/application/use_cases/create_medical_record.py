"""Use-case создания медицинской записи."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from app.application.dto.medical_record_view import MedicalRecordView
from app.application.ports.medical_record_repository import MedicalRecordRepositoryPort
from app.application.use_cases.medical_record_errors import (
    MedicalRecordAccessDeniedError,
    PatientPassportNotFoundError,
)


class CreateMedicalRecord:
    """Создать медицинскую запись и выдать ее проекцию для автора."""

    def __init__(self, repository: MedicalRecordRepositoryPort) -> None:
        """Инициализировать use-case.

        Args:
            repository: Репозиторий медицинских записей.
        """
        self._repository = repository

    def execute(
        self,
        actor_user_id: UUID,
        actor_role: str,
        patient_passport_id: UUID,
        record_type: str,
        event_date: date,
        title: str | None,
        payload_json: dict[str, object],
    ) -> MedicalRecordView:
        """Создать новую медицинскую запись.

        Args:
            actor_user_id: Идентификатор текущего пользователя.
            actor_role: Роль текущего пользователя.
            patient_passport_id: Идентификатор паспортной карточки пациента.
            record_type: Тип записи.
            event_date: Дата медицинского события.
            title: Заголовок записи.
            payload_json: Медицинское содержимое записи.

        Returns:
            DTO созданной записи.

        Raises:
            MedicalRecordAccessDeniedError: Если роль не может создать запись или пациент пишет не в свой паспорт.
            PatientPassportNotFoundError: Если указанный паспорт не найден.
        """
        if actor_role not in {'doctor', 'patient'}:
            raise MedicalRecordAccessDeniedError

        patient_passport = self._repository.get_patient_passport(patient_passport_id=patient_passport_id)
        if patient_passport is None:
            raise PatientPassportNotFoundError

        if actor_role == 'patient' and patient_passport.patient_user_id != actor_user_id:
            raise MedicalRecordAccessDeniedError

        accessible_record = self._repository.create_record(
            creator_user_id=actor_user_id,
            patient_passport_id=patient_passport_id,
            record_type=record_type,
            event_date=event_date,
            title=title,
            payload_json=payload_json,
        )
        return MedicalRecordView(
            id=accessible_record.record.id,
            creator_user_id=accessible_record.record.creator_user_id,
            status=accessible_record.record.status.value,
            record_type=accessible_record.record.record_type.value,
            event_date=accessible_record.record.event_date,
            title=accessible_record.record.title,
            payload_json=accessible_record.record.payload_json,
            patient_passport_id=accessible_record.patient_passport_id,
            created_at=accessible_record.record.created_at,
            updated_at=accessible_record.record.updated_at,
        )

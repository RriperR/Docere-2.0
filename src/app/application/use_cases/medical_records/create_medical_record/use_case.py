"""Сценарий создания медицинской записи."""

from __future__ import annotations

from app.application.ports.repositories.medical_records.port import MedicalRecordRepositoryPort
from app.application.use_cases.medical_records.common.dtos import MedicalRecordDTO
from app.application.use_cases.medical_records.create_medical_record.dtos import CreateMedicalRecordDTO
from app.application.use_cases.medical_records.errors import (
    MedicalRecordAccessDeniedError,
    PatientPassportNotFoundError,
)


class CreateMedicalRecordUseCase:
    """Создать медицинскую запись и выдать ее проекцию для автора."""

    def __init__(self, repository: MedicalRecordRepositoryPort) -> None:
        """Инициализировать use-case.

        Args:
            repository: Репозиторий медицинских записей.
        """
        self._repository = repository

    def execute(self, input_dto: CreateMedicalRecordDTO) -> MedicalRecordDTO:
        """Создать новую медицинскую запись.

        Args:
            input_dto: Входной DTO сценария.

        Returns:
            DTO созданной записи.

        Raises:
            MedicalRecordAccessDeniedError: Если роль не может создать запись
                или пациент пишет не в свой паспорт.
            PatientPassportNotFoundError: Если указанный паспорт не найден.
        """
        if input_dto.actor_role not in {'doctor', 'patient'}:
            raise MedicalRecordAccessDeniedError

        patient_passport = self._repository.get_patient_passport(
            patient_passport_id=input_dto.patient_passport_id,
        )
        if patient_passport is None:
            raise PatientPassportNotFoundError

        if input_dto.actor_role == 'patient' and patient_passport.patient_user_id != input_dto.actor_user_id:
            raise MedicalRecordAccessDeniedError

        accessible_record = self._repository.create_record(
            creator_user_id=input_dto.actor_user_id,
            patient_passport_id=input_dto.patient_passport_id,
            record_type=input_dto.record_type,
            event_date=input_dto.event_date,
            title=input_dto.title,
            payload_json=input_dto.payload_json,
        )
        return MedicalRecordDTO(
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

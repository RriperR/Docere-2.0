"""Сценарий получения медицинской записи."""

from __future__ import annotations

from app.application.ports.repositories.medical_records.port import MedicalRecordRepositoryPort
from app.application.use_cases.medical_records.common.dtos import MedicalRecordDTO
from app.application.use_cases.medical_records.errors import (
    MedicalRecordAccessDeniedError,
    MedicalRecordNotFoundError,
)
from app.application.use_cases.medical_records.get_medical_record.dtos import GetMedicalRecordDTO


class GetMedicalRecordUseCase:
    """Получить медицинскую запись по идентификатору для конкретного пользователя."""

    def __init__(self, repository: MedicalRecordRepositoryPort) -> None:
        """Инициализировать use-case.

        Args:
            repository: Репозиторий медицинских записей.
        """
        self._repository = repository

    def execute(self, input_dto: GetMedicalRecordDTO) -> MedicalRecordDTO:
        """Вернуть доступную пользователю медицинскую запись.

        Args:
            input_dto: Входной DTO сценария.

        Returns:
            DTO записи в контексте доступа пользователя.

        Raises:
            MedicalRecordNotFoundError: Если запись не существует.
            MedicalRecordAccessDeniedError: Если запись существует, но доступа нет.
        """
        accessible_record = self._repository.get_accessible_record(
            record_id=input_dto.record_id,
            user_id=input_dto.user_id,
        )
        if accessible_record is None:
            if self._repository.record_exists(record_id=input_dto.record_id):
                raise MedicalRecordAccessDeniedError
            raise MedicalRecordNotFoundError

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

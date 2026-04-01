"""Сценарий чтения медицинской записи."""

from __future__ import annotations

from app.application.ports.repositories.medical_records.port import MedicalRecordRepositoryPort
from app.application.use_cases.medical_records.common.dtos import MedicalRecordDTO
from app.application.use_cases.medical_records.create_medical_record.use_case import _to_medical_record_dto
from app.application.use_cases.medical_records.errors import (
    MedicalRecordAccessDeniedError,
    MedicalRecordNotFoundError,
)
from app.application.use_cases.medical_records.get_medical_record.dtos import GetMedicalRecordDTO


class GetMedicalRecordUseCase:
    """Вернуть медицинскую запись, если она доступна пользователю."""

    def __init__(self, repository: MedicalRecordRepositoryPort) -> None:
        """Инициализировать use case репозиторием медицинских записей."""
        self._repository = repository

    def execute(self, input_dto: GetMedicalRecordDTO) -> MedicalRecordDTO:
        """Вернуть detail-проекцию медицинской записи для пользователя.

        Returns:
            Detail-проекция медицинской записи.

        Raises:
            MedicalRecordAccessDeniedError: Если запись существует, но недоступна.
            MedicalRecordNotFoundError: Если запись не существует.
        """
        accessible_record = self._repository.get_accessible_record(
            record_id=input_dto.record_id,
            user_id=input_dto.user_id,
        )
        if accessible_record is None:
            if self._repository.record_exists(record_id=input_dto.record_id):
                raise MedicalRecordAccessDeniedError
            raise MedicalRecordNotFoundError

        return _to_medical_record_dto(accessible_record)

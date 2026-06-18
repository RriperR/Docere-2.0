"""Сценарий подтверждения медицинской записи."""

from __future__ import annotations

from uuid import UUID

from app.application.ports.repositories.medical_records.port import MedicalRecordRepositoryPort
from app.application.use_cases.medical_records.common.dtos import MedicalRecordDTO
from app.application.use_cases.medical_records.common.mappers import to_medical_record_dto
from app.application.use_cases.medical_records.errors import (
    MedicalRecordAccessDeniedError,
    MedicalRecordNotFoundError,
    MedicalRecordValidationError,
)


class ConfirmMedicalRecordUseCase:
    """Подтвердить медицинскую запись по разрешенной бизнес-схеме."""

    def __init__(self, repository: MedicalRecordRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий медицинских записей.
        """
        self._repository = repository

    def execute(self, *, record_id: UUID, actor_user_id: UUID, actor_role: str) -> MedicalRecordDTO:
        """Выполнить подтверждение записи.

        Args:
            record_id: Идентификатор записи.
            actor_user_id: Идентификатор текущего пользователя.
            actor_role: Роль текущего пользователя.

        Returns:
            Обновленная проекция записи.

        Raises:
            MedicalRecordNotFoundError: Если запись недоступна пользователю.
            MedicalRecordValidationError: Если запись уже подтверждена.
            MedicalRecordAccessDeniedError: Если пользователь не может подтвердить запись.
        """
        accessible_record = self._repository.get_accessible_record(record_id=record_id, user_id=actor_user_id)
        if accessible_record is None:
            raise MedicalRecordNotFoundError
        if accessible_record.record.status.value == 'confirmed':
            raise MedicalRecordValidationError

        confirmed_record = self._repository.confirm_record(
            record_id=record_id,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
        )
        if confirmed_record is None:
            raise MedicalRecordAccessDeniedError
        return to_medical_record_dto(confirmed_record)

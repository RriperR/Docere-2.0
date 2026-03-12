"""Use-case получения медицинской записи."""

from __future__ import annotations

from uuid import UUID

from app.application.dto.medical_record_view import MedicalRecordView
from app.application.ports.medical_record_repository import MedicalRecordRepositoryPort
from app.application.use_cases.medical_record_errors import (
    MedicalRecordAccessDeniedError,
    MedicalRecordNotFoundError,
)


class GetMedicalRecord:
    """Получить медицинскую запись по идентификатору для конкретного пользователя."""

    def __init__(self, repository: MedicalRecordRepositoryPort) -> None:
        """Инициализировать use-case.

        Args:
            repository: Репозиторий медицинских записей.
        """
        self._repository = repository

    def execute(self, record_id: UUID, user_id: UUID) -> MedicalRecordView:
        """Вернуть доступную пользователю медицинскую запись.

        Args:
            record_id: Идентификатор записи.
            user_id: Идентификатор пользователя.

        Returns:
            DTO записи в контексте доступа пользователя.

        Raises:
            MedicalRecordNotFoundError: Если запись не существует.
            MedicalRecordAccessDeniedError: Если запись существует, но доступа нет.
        """
        accessible_record = self._repository.get_accessible_record(record_id=record_id, user_id=user_id)
        if accessible_record is None:
            if self._repository.record_exists(record_id=record_id):
                raise MedicalRecordAccessDeniedError
            raise MedicalRecordNotFoundError

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

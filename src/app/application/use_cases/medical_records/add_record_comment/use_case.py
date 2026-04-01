"""Сценарий создания комментариев к записи."""

from __future__ import annotations

from app.application.ports.repositories.medical_records.port import MedicalRecordRepositoryPort
from app.application.use_cases.medical_records.add_record_comment.dtos import AddRecordCommentDTO
from app.application.use_cases.medical_records.common.dtos import RecordCommentDTO
from app.application.use_cases.medical_records.errors import (
    MedicalRecordAccessDeniedError,
    MedicalRecordNotFoundError,
)


class AddRecordCommentUseCase:
    """Добавить комментарий врача или администратора к доступной записи."""

    def __init__(self, repository: MedicalRecordRepositoryPort) -> None:
        """Инициализировать use case репозиторием медицинских записей."""
        self._repository = repository

    def execute(self, input_dto: AddRecordCommentDTO) -> RecordCommentDTO:
        """Создать комментарий, если роль и доступ пользователя допустимы.

        Returns:
            Проекция созданного комментария.

        Raises:
            MedicalRecordAccessDeniedError: Если роль или доступ к записи некорректны.
            MedicalRecordNotFoundError: Если целевая запись не существует.
        """
        if input_dto.actor_role not in {'doctor', 'admin'}:
            raise MedicalRecordAccessDeniedError

        accessible_record = self._repository.get_accessible_record(
            record_id=input_dto.record_id,
            user_id=input_dto.actor_user_id,
        )
        if accessible_record is None:
            if self._repository.record_exists(record_id=input_dto.record_id):
                raise MedicalRecordAccessDeniedError
            raise MedicalRecordNotFoundError

        comment = self._repository.add_comment(
            record_id=input_dto.record_id,
            author_user_id=input_dto.actor_user_id,
            body=input_dto.body,
        )
        return RecordCommentDTO(
            id=comment.id,
            record_id=comment.record_id,
            author_user_id=comment.author_user_id,
            body=comment.body,
            created_at=comment.created_at,
        )

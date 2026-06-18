"""Сценарий загрузки вложения к медицинской записи."""

from __future__ import annotations

from uuid import uuid4

from app.application.ports.repositories.medical_records.port import MedicalRecordRepositoryPort
from app.application.ports.storage.file_storage import FileStoragePort
from app.application.use_cases.medical_records.common.dtos import FileAttachmentDTO
from app.application.use_cases.medical_records.common.mappers import to_file_attachment_dto
from app.application.use_cases.medical_records.errors import (
    MedicalRecordAccessDeniedError,
    MedicalRecordNotFoundError,
)
from app.application.use_cases.medical_records.record_attachments.dtos import AddRecordAttachmentDTO

_RECORD_ATTACHMENT_CATEGORY = 'document'


class AddRecordAttachmentUseCase:
    """Загрузить файл и привязать его к медицинской записи."""

    def __init__(self, repository: MedicalRecordRepositoryPort, storage: FileStoragePort) -> None:
        """Инициализировать use case репозиторием и файловым хранилищем."""
        self._repository = repository
        self._storage = storage

    def execute(self, input_dto: AddRecordAttachmentDTO) -> FileAttachmentDTO:
        """Сохранить вложение записи.

        Прикрепить файл может любой пользователь, у которого есть доступ к записи
        (в том числе её владелец-пациент и врач с доступом).

        Returns:
            Проекция созданного вложения.

        Raises:
            MedicalRecordAccessDeniedError: Если запись недоступна пользователю.
            MedicalRecordNotFoundError: Если запись не существует.
        """
        accessible_record = self._repository.get_accessible_record(
            record_id=input_dto.record_id,
            user_id=input_dto.actor_user_id,
        )
        if accessible_record is None:
            if self._repository.record_exists(record_id=input_dto.record_id):
                raise MedicalRecordAccessDeniedError
            raise MedicalRecordNotFoundError

        storage_key = f'records/{input_dto.record_id}/{uuid4().hex}/{input_dto.filename}'
        self._storage.upload(
            key=storage_key,
            content=input_dto.content,
            content_type=input_dto.content_type,
        )

        attachment = self._repository.add_attachment(
            record_id=input_dto.record_id,
            comment_id=None,
            uploaded_by_user_id=input_dto.actor_user_id,
            category=_RECORD_ATTACHMENT_CATEGORY,
            filename=input_dto.filename,
            storage_key=storage_key,
            mime_type=input_dto.content_type,
            size_bytes=len(input_dto.content),
        )
        return to_file_attachment_dto(attachment)

"""Сценарии загрузки и скачивания вложений комментариев."""

from __future__ import annotations

from uuid import uuid4

from app.application.ports.repositories.medical_records.port import MedicalRecordRepositoryPort
from app.application.ports.storage.file_storage import FileStoragePort
from app.application.use_cases.medical_records.comment_attachments.dtos import (
    AddCommentAttachmentDTO,
    AttachmentContentDTO,
    DownloadAttachmentDTO,
)
from app.application.use_cases.medical_records.common.dtos import FileAttachmentDTO
from app.application.use_cases.medical_records.common.mappers import to_file_attachment_dto
from app.application.use_cases.medical_records.errors import (
    FileAttachmentNotFoundError,
    MedicalRecordAccessDeniedError,
    MedicalRecordNotFoundError,
    RecordCommentNotFoundError,
)

_COMMENT_ATTACHMENT_CATEGORY = 'document'


class AddCommentAttachmentUseCase:
    """Загрузить файл и привязать его к комментарию записи."""

    def __init__(self, repository: MedicalRecordRepositoryPort, storage: FileStoragePort) -> None:
        """Инициализировать use case репозиторием и файловым хранилищем."""
        self._repository = repository
        self._storage = storage

    def execute(self, input_dto: AddCommentAttachmentDTO) -> FileAttachmentDTO:
        """Сохранить вложение комментария.

        Returns:
            Проекция созданного вложения.

        Raises:
            MedicalRecordAccessDeniedError: Если роль или доступ к записи некорректны.
            MedicalRecordNotFoundError: Если запись не существует.
            RecordCommentNotFoundError: Если комментарий не относится к записи.
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

        if not self._repository.comment_belongs_to_record(
            comment_id=input_dto.comment_id,
            record_id=input_dto.record_id,
        ):
            raise RecordCommentNotFoundError

        storage_key = (
            f'records/{input_dto.record_id}/comments/{input_dto.comment_id}/{uuid4().hex}/{input_dto.filename}'
        )
        self._storage.upload(
            key=storage_key,
            content=input_dto.content,
            content_type=input_dto.content_type,
        )

        attachment = self._repository.add_attachment(
            record_id=input_dto.record_id,
            comment_id=input_dto.comment_id,
            uploaded_by_user_id=input_dto.actor_user_id,
            uploaded_by_fio=input_dto.actor_fio,
            category=_COMMENT_ATTACHMENT_CATEGORY,
            filename=input_dto.filename,
            storage_key=storage_key,
            mime_type=input_dto.content_type,
            size_bytes=len(input_dto.content),
        )
        return to_file_attachment_dto(attachment)


class DownloadAttachmentUseCase:
    """Вернуть содержимое вложения, если запись доступна пользователю."""

    def __init__(self, repository: MedicalRecordRepositoryPort, storage: FileStoragePort) -> None:
        """Инициализировать use case репозиторием и файловым хранилищем."""
        self._repository = repository
        self._storage = storage

    def execute(self, input_dto: DownloadAttachmentDTO) -> AttachmentContentDTO:
        """Вернуть содержимое вложения.

        Returns:
            Содержимое вложения с именем файла и MIME-типом.

        Raises:
            FileAttachmentNotFoundError: Если вложение не существует.
            MedicalRecordAccessDeniedError: Если запись вложения недоступна пользователю.
        """
        attachment = self._repository.get_attachment(attachment_id=input_dto.attachment_id)
        if attachment is None:
            raise FileAttachmentNotFoundError

        accessible_record = self._repository.get_accessible_record(
            record_id=attachment.record_id,
            user_id=input_dto.actor_user_id,
        )
        if accessible_record is None:
            raise MedicalRecordAccessDeniedError

        content = self._storage.download(key=attachment.storage_key)
        return AttachmentContentDTO(
            filename=attachment.filename or attachment.storage_key.rsplit('/', maxsplit=1)[-1],
            mime_type=attachment.mime_type,
            content=content,
        )

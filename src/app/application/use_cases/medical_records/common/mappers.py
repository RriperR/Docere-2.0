"""Мапперы доменных сущностей медицинских записей в проекции."""

from __future__ import annotations

from app.application.use_cases.medical_records.common.dtos import FileAttachmentDTO, RecordCommentDTO
from app.domain.entities.file_attachment import FileAttachment
from app.domain.entities.record_comment import RecordComment


def to_file_attachment_dto(attachment: FileAttachment) -> FileAttachmentDTO:
    """Преобразовать доменное вложение в проекцию.

    Args:
        attachment: Доменная сущность вложения.

    Returns:
        Проекция вложения.
    """
    return FileAttachmentDTO(
        id=attachment.id,
        record_id=attachment.record_id,
        comment_id=attachment.comment_id,
        uploaded_by_user_id=attachment.uploaded_by_user_id,
        category=attachment.category.value,
        filename=attachment.filename,
        storage_key=attachment.storage_key,
        mime_type=attachment.mime_type,
        size_bytes=attachment.size_bytes,
        uploaded_at=attachment.uploaded_at,
    )


def to_record_comment_dto(comment: RecordComment) -> RecordCommentDTO:
    """Преобразовать доменный комментарий в проекцию.

    Args:
        comment: Доменная сущность комментария.

    Returns:
        Проекция комментария вместе с вложениями.
    """
    return RecordCommentDTO(
        id=comment.id,
        record_id=comment.record_id,
        author_user_id=comment.author_user_id,
        author_fio=comment.author_fio,
        author_role=comment.author_role,
        body=comment.body,
        attachments=tuple(to_file_attachment_dto(attachment) for attachment in comment.attachments),
        created_at=comment.created_at,
    )

"""Мапперы доменных сущностей медицинских записей в проекции."""

from __future__ import annotations

from app.application.ports.repositories.medical_records.dtos import AccessibleMedicalRecordDTO
from app.application.use_cases.medical_records.common.dtos import (
    FileAttachmentDTO,
    MedicalRecordDTO,
    PractitionerPassportDTO,
    RecordCommentDTO,
)
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
        uploaded_by_fio=attachment.uploaded_by_fio,
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


def to_medical_record_dto(accessible_record: AccessibleMedicalRecordDTO) -> MedicalRecordDTO:
    """Преобразовать доступную запись в API-проекцию.

    Args:
        accessible_record: Запись с контекстом доступа пользователя.

    Returns:
        Проекция медицинской записи.
    """
    record = accessible_record.record
    author_practitioner = accessible_record.author_practitioner_passport
    comments = tuple(to_record_comment_dto(comment) for comment in accessible_record.comments)
    attachments = tuple(to_file_attachment_dto(attachment) for attachment in accessible_record.attachments)
    return MedicalRecordDTO(
        id=record.id,
        creator_user_id=record.creator_user_id,
        author_practitioner_passport_id=record.author_practitioner_passport_id,
        status=record.status.value,
        record_type=record.record_type.value,
        event_date=record.event_date,
        title=record.title,
        appointment_location=record.appointment_location,
        clinical_summary=record.clinical_summary,
        payload_json=record.payload_json,
        confirmed_by_user_id=record.confirmed_by_user_id,
        confirmed_at=record.confirmed_at,
        patient_passport_id=accessible_record.patient_passport_id,
        author_practitioner_passport=(
            PractitionerPassportDTO(
                id=author_practitioner.id,
                user_id=author_practitioner.user_id,
                full_name=author_practitioner.full_name,
                specialty=author_practitioner.specialty,
                organization=author_practitioner.organization,
                position=author_practitioner.position,
                email=author_practitioner.email,
                phone=author_practitioner.phone,
                status=author_practitioner.status.value,
            )
            if author_practitioner is not None
            else None
        ),
        comments=comments,
        attachments=attachments,
        comments_count=len(comments),
        attachments_count=len(attachments),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )

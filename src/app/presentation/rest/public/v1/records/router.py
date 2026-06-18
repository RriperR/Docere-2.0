"""REST-роуты медицинских записей."""

from __future__ import annotations

from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Response, status, UploadFile
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.medical_records.add_record_comment.dtos import AddRecordCommentDTO
from app.application.use_cases.medical_records.add_record_comment.use_case import AddRecordCommentUseCase
from app.application.use_cases.medical_records.comment_attachments.dtos import (
    AddCommentAttachmentDTO,
    DownloadAttachmentDTO,
)
from app.application.use_cases.medical_records.comment_attachments.use_cases import (
    AddCommentAttachmentUseCase,
    DownloadAttachmentUseCase,
)
from app.application.use_cases.medical_records.common.dtos import (
    FileAttachmentDTO,
    MedicalRecordDTO,
    RecordCommentDTO,
)
from app.application.use_cases.medical_records.create_medical_record.dtos import CreateMedicalRecordDTO
from app.application.use_cases.medical_records.create_medical_record.use_case import CreateMedicalRecordUseCase
from app.application.use_cases.medical_records.errors import (
    FileAttachmentNotFoundError,
    MedicalRecordAccessDeniedError,
    MedicalRecordNotFoundError,
    MedicalRecordValidationError,
    PatientPassportNotFoundError,
    PractitionerPassportNotFoundError,
    RecordCommentNotFoundError,
)
from app.application.use_cases.medical_records.get_medical_record.dtos import GetMedicalRecordDTO
from app.application.use_cases.medical_records.get_medical_record.use_case import GetMedicalRecordUseCase
from app.application.use_cases.medical_records.record_attachments.dtos import AddRecordAttachmentDTO
from app.application.use_cases.medical_records.record_attachments.use_cases import AddRecordAttachmentUseCase
from app.presentation.rest.public.v1.records.dependencies import (
    add_comment_attachment_use_case_dependency,
    add_record_attachment_use_case_dependency,
    add_record_comment_use_case_dependency,
    create_medical_record_use_case_dependency,
    current_authenticated_user_dependency,
    db_session_dependency,
    download_attachment_use_case_dependency,
    get_medical_record_use_case_dependency,
)
from app.presentation.rest.public.v1.records.schemas import (
    CreateMedicalRecordRequestSchema,
    CreateRecordCommentRequestSchema,
    FileAttachmentResponseSchema,
    MedicalRecordResponseSchema,
    RecordCommentResponseSchema,
)
from app.presentation.webserver.http_errors import raise_forbidden, raise_not_found

router = APIRouter(prefix='/records', tags=['records'])

uploaded_file_dependency = File(...)


@router.post('', response_model=MedicalRecordResponseSchema, status_code=status.HTTP_201_CREATED)
def create_medical_record(
    payload: CreateMedicalRecordRequestSchema,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: CreateMedicalRecordUseCase = create_medical_record_use_case_dependency,
    session: Session = db_session_dependency,
) -> MedicalRecordDTO:
    """Создать медицинскую запись для текущего пользователя.

    Returns:
        Detail созданной медицинской записи.

    Raises:
        HTTPException: Если не найден паспорт или не пройдены проверки доступа.
    """
    try:
        record = use_case.execute(
            CreateMedicalRecordDTO(
                actor_user_id=current_user.id,
                actor_role=current_user.role,
                actor_fio=current_user.fio,
                actor_email=current_user.email,
                actor_phone=current_user.phone,
                patient_passport_id=payload.patient_passport_id,
                author_practitioner_passport_id=payload.author_practitioner_passport_id,
                author_practitioner_full_name=payload.author_practitioner_full_name,
                author_practitioner_specialty=payload.author_practitioner_specialty,
                author_practitioner_organization=payload.author_practitioner_organization,
                author_practitioner_position=payload.author_practitioner_position,
                author_practitioner_email=payload.author_practitioner_email,
                author_practitioner_phone=payload.author_practitioner_phone,
                record_type=payload.record_type,
                event_date=payload.event_date,
                title=payload.title,
                appointment_location=payload.appointment_location,
                clinical_summary=payload.clinical_summary,
                payload_json=payload.payload_json,
            ),
        )
        session.commit()
        return record
    except PatientPassportNotFoundError:
        session.rollback()
        raise_not_found('Patient passport not found')
    except PractitionerPassportNotFoundError:
        session.rollback()
        raise_not_found('Practitioner passport not found')
    except MedicalRecordValidationError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Practitioner passport or practitioner full name is required',
        ) from exc
    except MedicalRecordAccessDeniedError:
        session.rollback()
        raise_forbidden('You do not have access to create a record for this patient passport')
    except Exception:
        session.rollback()
        raise


@router.get('/{record_id}', response_model=MedicalRecordResponseSchema)
def get_medical_record(
    record_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: GetMedicalRecordUseCase = get_medical_record_use_case_dependency,
) -> MedicalRecordDTO:
    """Вернуть detail медицинской записи для текущего пользователя.

    Returns:
        Detail-проекция медицинской записи.
    """
    try:
        return use_case.execute(GetMedicalRecordDTO(record_id=record_id, user_id=current_user.id))
    except MedicalRecordNotFoundError:
        raise_not_found('Medical record not found')
    except MedicalRecordAccessDeniedError:
        raise_forbidden('You do not have access to this medical record')


@router.post(
    '/{record_id}/attachments',
    response_model=FileAttachmentResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def add_record_attachment(
    record_id: UUID,
    file: UploadFile = uploaded_file_dependency,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: AddRecordAttachmentUseCase = add_record_attachment_use_case_dependency,
    session: Session = db_session_dependency,
) -> FileAttachmentDTO:
    """Прикрепить файл к медицинской записи.

    Returns:
        Проекция созданного вложения.
    """
    content = file.file.read()
    try:
        attachment = use_case.execute(
            AddRecordAttachmentDTO(
                record_id=record_id,
                actor_user_id=current_user.id,
                actor_fio=current_user.fio,
                filename=file.filename or 'file',
                content=content,
                content_type=file.content_type or 'application/octet-stream',
            ),
        )
        session.commit()
        return attachment
    except MedicalRecordNotFoundError:
        session.rollback()
        raise_not_found('Medical record not found')
    except MedicalRecordAccessDeniedError:
        session.rollback()
        raise_forbidden('You do not have access to attach files to this record')
    except Exception:
        session.rollback()
        raise


@router.post(
    '/{record_id}/comments',
    response_model=RecordCommentResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def add_record_comment(
    record_id: UUID,
    payload: CreateRecordCommentRequestSchema,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: AddRecordCommentUseCase = add_record_comment_use_case_dependency,
    session: Session = db_session_dependency,
) -> RecordCommentDTO:
    """Добавить комментарий врача или администратора к медицинской записи.

    Returns:
        Проекция созданного комментария.
    """
    try:
        comment = use_case.execute(
            AddRecordCommentDTO(
                record_id=record_id,
                actor_user_id=current_user.id,
                actor_role=current_user.role,
                actor_fio=current_user.fio,
                body=payload.body,
            ),
        )
        session.commit()
        return comment
    except MedicalRecordNotFoundError:
        session.rollback()
        raise_not_found('Medical record not found')
    except MedicalRecordAccessDeniedError:
        session.rollback()
        raise_forbidden('You do not have access to comment on this medical record')
    except Exception:
        session.rollback()
        raise


@router.post(
    '/{record_id}/comments/{comment_id}/attachments',
    response_model=FileAttachmentResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def add_comment_attachment(
    record_id: UUID,
    comment_id: UUID,
    file: UploadFile = uploaded_file_dependency,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: AddCommentAttachmentUseCase = add_comment_attachment_use_case_dependency,
    session: Session = db_session_dependency,
) -> FileAttachmentDTO:
    """Загрузить файл и привязать его к комментарию записи.

    Returns:
        Проекция созданного вложения.
    """
    content = file.file.read()
    try:
        attachment = use_case.execute(
            AddCommentAttachmentDTO(
                record_id=record_id,
                comment_id=comment_id,
                actor_user_id=current_user.id,
                actor_role=current_user.role,
                actor_fio=current_user.fio,
                filename=file.filename or 'file',
                content=content,
                content_type=file.content_type or 'application/octet-stream',
            ),
        )
        session.commit()
        return attachment
    except MedicalRecordNotFoundError:
        session.rollback()
        raise_not_found('Medical record not found')
    except RecordCommentNotFoundError:
        session.rollback()
        raise_not_found('Comment not found')
    except MedicalRecordAccessDeniedError:
        session.rollback()
        raise_forbidden('You do not have access to attach files to this comment')
    except Exception:
        session.rollback()
        raise


@router.get('/{record_id}/attachments/{attachment_id}')
def download_attachment(
    record_id: UUID,
    attachment_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: DownloadAttachmentUseCase = download_attachment_use_case_dependency,
) -> Response:
    """Скачать содержимое вложения.

    Returns:
        Бинарный ответ с содержимым вложения.
    """
    try:
        result = use_case.execute(
            DownloadAttachmentDTO(attachment_id=attachment_id, actor_user_id=current_user.id),
        )
    except FileAttachmentNotFoundError:
        raise_not_found('Attachment not found')
    except MedicalRecordAccessDeniedError:
        raise_forbidden('You do not have access to this attachment')

    disposition = f"attachment; filename*=UTF-8''{quote(result.filename)}"
    return Response(
        content=result.content,
        media_type=result.mime_type,
        headers={'Content-Disposition': disposition},
    )

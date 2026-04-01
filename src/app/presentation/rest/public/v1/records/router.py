"""REST-роуты медицинских записей."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.medical_records.add_record_comment.dtos import AddRecordCommentDTO
from app.application.use_cases.medical_records.add_record_comment.use_case import AddRecordCommentUseCase
from app.application.use_cases.medical_records.common.dtos import MedicalRecordDTO, RecordCommentDTO
from app.application.use_cases.medical_records.create_medical_record.dtos import CreateMedicalRecordDTO
from app.application.use_cases.medical_records.create_medical_record.use_case import CreateMedicalRecordUseCase
from app.application.use_cases.medical_records.errors import (
    MedicalRecordAccessDeniedError,
    MedicalRecordNotFoundError,
    MedicalRecordValidationError,
    PatientPassportNotFoundError,
    PractitionerPassportNotFoundError,
)
from app.application.use_cases.medical_records.get_medical_record.dtos import GetMedicalRecordDTO
from app.application.use_cases.medical_records.get_medical_record.use_case import GetMedicalRecordUseCase
from app.presentation.rest.public.v1.records.dependencies import (
    add_record_comment_use_case_dependency,
    create_medical_record_use_case_dependency,
    current_authenticated_user_dependency,
    db_session_dependency,
    get_medical_record_use_case_dependency,
)
from app.presentation.rest.public.v1.records.schemas import (
    CreateMedicalRecordRequestSchema,
    CreateRecordCommentRequestSchema,
    MedicalRecordResponseSchema,
    RecordCommentResponseSchema,
)
from app.presentation.webserver.http_errors import raise_forbidden, raise_not_found

router = APIRouter(prefix='/records', tags=['records'])


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

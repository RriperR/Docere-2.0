"""REST-роуты для медицинских записей."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.medical_records.common.dtos import MedicalRecordDTO
from app.application.use_cases.medical_records.create_medical_record.dtos import CreateMedicalRecordDTO
from app.application.use_cases.medical_records.create_medical_record.use_case import CreateMedicalRecordUseCase
from app.application.use_cases.medical_records.errors import (
    MedicalRecordAccessDeniedError,
    MedicalRecordNotFoundError,
    PatientPassportNotFoundError,
)
from app.application.use_cases.medical_records.get_medical_record.dtos import GetMedicalRecordDTO
from app.application.use_cases.medical_records.get_medical_record.use_case import GetMedicalRecordUseCase
from app.presentation.rest.public.v1.records.dependencies import (
    create_medical_record_use_case_dependency,
    current_authenticated_user_dependency,
    db_session_dependency,
    get_medical_record_use_case_dependency,
)
from app.presentation.rest.public.v1.records.schemas import (
    CreateMedicalRecordRequestSchema,
    MedicalRecordResponseSchema,
)
from app.presentation.webserver.http_errors import raise_forbidden, raise_not_found

router = APIRouter(prefix='/records', tags=['records'])


@router.post(
    '',
    response_model=MedicalRecordResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_medical_record(
    payload: CreateMedicalRecordRequestSchema,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: CreateMedicalRecordUseCase = create_medical_record_use_case_dependency,
    session: Session = db_session_dependency,
) -> MedicalRecordDTO:
    """Создать медицинскую запись.

    Args:
        payload: Тело запроса на создание записи.
        current_user: Текущий аутентифицированный пользователь.
        use_case: Use case создания записи.
        session: Активная сессия БД для фиксации изменений.

    Returns:
        Созданная медицинская запись.
    """
    try:
        record = use_case.execute(
            CreateMedicalRecordDTO(
                actor_user_id=current_user.id,
                actor_role=current_user.role,
                patient_passport_id=payload.patient_passport_id,
                record_type=payload.record_type,
                event_date=payload.event_date,
                title=payload.title,
                payload_json=payload.payload_json,
            ),
        )
        session.commit()
        return record
    except PatientPassportNotFoundError:
        session.rollback()
        raise_not_found('Patient passport not found')
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
    """Получить медицинскую запись по идентификатору.

    Args:
        record_id: Идентификатор записи.
        current_user: Текущий аутентифицированный пользователь.
        use_case: Use case получения записи.

    Returns:
        Медицинская запись в контексте доступа пользователя.
    """
    try:
        return use_case.execute(
            GetMedicalRecordDTO(record_id=record_id, user_id=current_user.id),
        )
    except MedicalRecordNotFoundError:
        raise_not_found('Medical record not found')
    except MedicalRecordAccessDeniedError:
        raise_forbidden('You do not have access to this medical record')

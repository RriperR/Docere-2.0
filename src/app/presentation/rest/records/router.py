"""REST-роуты для медицинских записей."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.application.dto.auth_user_view import AuthUserView
from app.application.dto.medical_record_view import MedicalRecordView
from app.application.use_cases.create_medical_record import CreateMedicalRecord
from app.application.use_cases.get_medical_record import GetMedicalRecord
from app.application.use_cases.medical_record_errors import (
    MedicalRecordAccessDeniedError,
    MedicalRecordNotFoundError,
    PatientPassportNotFoundError,
)
from app.presentation.rest.records.dependencies import (
    create_medical_record_use_case_dependency,
    current_authenticated_user_dependency,
    get_medical_record_use_case_dependency,
)
from app.presentation.rest.records.schemas import (
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
    current_user: AuthUserView = current_authenticated_user_dependency,
    use_case: CreateMedicalRecord = create_medical_record_use_case_dependency,
) -> MedicalRecordView:
    """Создать медицинскую запись.

    Args:
        payload: Тело запроса на создание записи.
        current_user: Текущий аутентифицированный пользователь.
        use_case: Use-case создания записи.

    Returns:
        Созданная медицинская запись.
    """
    try:
        return use_case.execute(
            actor_user_id=current_user.id,
            actor_role=current_user.role,
            patient_passport_id=payload.patient_passport_id,
            record_type=payload.record_type,
            event_date=payload.event_date,
            title=payload.title,
            payload_json=payload.payload_json,
        )
    except PatientPassportNotFoundError:
        raise_not_found('Patient passport not found')
    except MedicalRecordAccessDeniedError:
        raise_forbidden('You do not have access to create a record for this patient passport')


@router.get('/{record_id}', response_model=MedicalRecordResponseSchema)
def get_medical_record(
    record_id: UUID,
    current_user: AuthUserView = current_authenticated_user_dependency,
    use_case: GetMedicalRecord = get_medical_record_use_case_dependency,
) -> MedicalRecordView:
    """Получить медицинскую запись по идентификатору.

    Args:
        record_id: Идентификатор записи.
        current_user: Текущий аутентифицированный пользователь.
        use_case: Use-case получения записи.

    Returns:
        Медицинская запись в контексте доступа пользователя.
    """
    try:
        return use_case.execute(record_id=record_id, user_id=current_user.id)
    except MedicalRecordNotFoundError:
        raise_not_found('Medical record not found')
    except MedicalRecordAccessDeniedError:
        raise_forbidden('You do not have access to this medical record')

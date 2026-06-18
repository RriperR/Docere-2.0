"""REST-роуты пациентов."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query, status
from sqlalchemy.orm import Session

from app.application.ports.repositories.patient_cards.dtos import (
    PatientRecordSummaryDTO,
    PatientSearchResultDTO,
    PatientSummaryDTO,
)
from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.patients.create_patient import CreatePatientUseCase
from app.application.use_cases.patients.errors import (
    PatientCardAccessDeniedError,
    PatientCardNotFoundError,
)
from app.application.use_cases.patients.get_patient import GetPatientUseCase
from app.application.use_cases.patients.list_patient_records import ListPatientRecordsUseCase
from app.application.use_cases.patients.list_patients import ListPatientsUseCase
from app.application.use_cases.patients.search_patients import SearchPatientsUseCase
from app.presentation.rest.public.v1.patients.schemas import (
    CreatePatientRequestSchema,
    PatientRecordSummaryResponseSchema,
    PatientSearchResultResponseSchema,
    PatientSummaryResponseSchema,
)
from app.presentation.rest.public.v1.records.dependencies import (
    create_patient_use_case_dependency,
    current_authenticated_user_dependency,
    db_session_dependency,
    get_patient_use_case_dependency,
    list_patient_records_use_case_dependency,
    list_patients_use_case_dependency,
    search_patients_use_case_dependency,
)
from app.presentation.webserver.http_errors import raise_forbidden, raise_not_found

router = APIRouter(prefix='/patients', tags=['patients'])


@router.get('', response_model=list[PatientSummaryResponseSchema])
def list_patients(
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ListPatientsUseCase = list_patients_use_case_dependency,
) -> tuple[PatientSummaryDTO, ...]:
    """Вернуть список доступных пользователю паспортов пациентов.

    Returns:
        Список кратких карточек доступных пациентов.
    """
    return use_case.execute(user_id=current_user.id, user_role=current_user.role)


@router.get('/search', response_model=list[PatientSearchResultResponseSchema])
def search_patients(
    q: str = Query(min_length=1, max_length=255),
    date_of_birth: date | None = None,
    limit: int = Query(default=10, ge=1, le=50),
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: SearchPatientsUseCase = search_patients_use_case_dependency,
) -> tuple[PatientSearchResultDTO, ...]:
    """Найти вероятные совпадения паспортов пациентов.

    Returns:
        Список кандидатов с оценкой похожести.
    """
    try:
        return use_case.execute(
            actor_user_id=current_user.id,
            actor_role=current_user.role,
            query=q,
            date_of_birth=date_of_birth,
            limit=limit,
        )
    except PatientCardAccessDeniedError:
        raise_forbidden('Only doctor or admin can search patient passports')


@router.post('', response_model=PatientSummaryResponseSchema, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: CreatePatientRequestSchema,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: CreatePatientUseCase = create_patient_use_case_dependency,
    session: Session = db_session_dependency,
) -> PatientSummaryDTO:
    """Создать паспорт пациента для врача или администратора.

    Returns:
        Краткая карточка созданного пациента.
    """
    try:
        patient = use_case.execute(
            actor_user_id=current_user.id,
            actor_role=current_user.role,
            fio=payload.fio,
            date_of_birth=payload.date_of_birth,
            email=str(payload.email).lower() if payload.email is not None else None,
            phone=payload.phone,
        )
        session.commit()
        return patient
    except PatientCardAccessDeniedError:
        session.rollback()
        raise_forbidden('Only doctor or admin can create patient passports')
    except Exception:
        session.rollback()
        raise


@router.get('/{patient_id}', response_model=PatientSummaryResponseSchema)
def get_patient(
    patient_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: GetPatientUseCase = get_patient_use_case_dependency,
) -> PatientSummaryDTO:
    """Вернуть детальную карточку пациента, доступную пользователю.

    Returns:
        Краткая карточка пациента для детальной страницы.
    """
    try:
        return use_case.execute(patient_id=patient_id, user_id=current_user.id, user_role=current_user.role)
    except PatientCardNotFoundError:
        raise_not_found('Patient not found')


@router.get('/{patient_id}/records', response_model=list[PatientRecordSummaryResponseSchema])
def list_patient_records(
    patient_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ListPatientRecordsUseCase = list_patient_records_use_case_dependency,
) -> tuple[PatientRecordSummaryDTO, ...]:
    """Вернуть записи доступной карточки пациента.

    Returns:
        Список кратких проекций медицинских записей пациента.
    """
    try:
        return use_case.execute(patient_id=patient_id, user_id=current_user.id, user_role=current_user.role)
    except PatientCardNotFoundError:
        raise_not_found('Patient not found')

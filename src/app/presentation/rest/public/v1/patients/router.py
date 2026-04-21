"""REST-роуты пациентов."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import func, or_, Select, select
from sqlalchemy.orm import Session

from app.application.ports.repositories.medical_records.dtos import AccessibleMedicalRecordDTO
from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.medical_records.common.dtos import PractitionerPassportDTO
from app.application.use_cases.medical_records.create_medical_record.use_case import (
    _to_medical_record_dto,
)
from app.infrastructure.adapters.repositories.medical_records.sqlalchemy_medical_record_repository import (
    SqlAlchemyMedicalRecordRepositoryAdapter,
)
from app.infrastructure.db.models.medical_records.medical_record import MedicalRecordRow
from app.infrastructure.db.models.medical_records.patient_passport import (
    PatientPassportRow,
    PatientPassportStatusRow,
)
from app.infrastructure.db.models.medical_records.user_record_link import UserRecordLinkRow
from app.presentation.rest.public.v1.patients.schemas import (
    CreatePatientRequestSchema,
    PatientRecordSummaryResponseSchema,
    PatientSummaryResponseSchema,
)
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
)
from app.presentation.rest.public.v1.records.schemas import PractitionerPassportResponseSchema
from app.presentation.webserver.http_errors import raise_forbidden, raise_not_found

router = APIRouter(prefix='/patients', tags=['patients'])


@router.get('', response_model=list[PatientSummaryResponseSchema])
def list_patients(
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    session: Session = db_session_dependency,
) -> list[PatientSummaryResponseSchema]:
    """Вернуть список доступных пользователю паспортов пациентов.

    Returns:
        Список кратких карточек доступных пациентов.
    """
    passport_rows = session.scalars(_accessible_patient_passports_query(current_user)).all()
    return [_to_patient_summary(row, current_user, session) for row in passport_rows]


@router.post('', response_model=PatientSummaryResponseSchema, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: CreatePatientRequestSchema,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    session: Session = db_session_dependency,
) -> PatientSummaryResponseSchema:
    """Создать паспорт пациента для врача или администратора.

    Returns:
        Краткая карточка созданного пациента.
    """
    if current_user.role not in {'doctor', 'admin'}:
        raise_forbidden('Only doctor or admin can create patient passports')

    patient_row = PatientPassportRow(
        created_by_user_id=current_user.id,
        patient_user_id=None,
        fio=payload.fio.strip(),
        date_of_birth=payload.date_of_birth,
        email=str(payload.email).lower() if payload.email is not None else None,
        phone=payload.phone,
        status=PatientPassportStatusRow.DRAFT,
    )
    session.add(patient_row)
    session.commit()
    session.refresh(patient_row)
    return _to_patient_summary(patient_row, current_user, session)


@router.get('/{patient_id}', response_model=PatientSummaryResponseSchema)
def get_patient(
    patient_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    session: Session = db_session_dependency,
) -> PatientSummaryResponseSchema:
    """Вернуть детальную карточку доступного пользователю пациента.

    Returns:
        Краткая карточка пациента для детальной страницы.
    """
    passport_row = _get_accessible_patient_passport(patient_id, current_user, session)
    if passport_row is None:
        raise_not_found('Patient not found')
    return _to_patient_summary(passport_row, current_user, session)


@router.get('/{patient_id}/records', response_model=list[PatientRecordSummaryResponseSchema])
def list_patient_records(
    patient_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    session: Session = db_session_dependency,
) -> list[PatientRecordSummaryResponseSchema]:
    """Вернуть записи доступной карточки пациента.

    Returns:
        Список кратких проекций медицинских записей пациента.
    """
    passport_row = _get_accessible_patient_passport(patient_id, current_user, session)
    if passport_row is None:
        raise_not_found('Patient not found')

    repository = SqlAlchemyMedicalRecordRepositoryAdapter(session=session)
    record_ids = session.scalars(
        select(UserRecordLinkRow.record_id)
        .join(MedicalRecordRow, MedicalRecordRow.id == UserRecordLinkRow.record_id)
        .where(
            UserRecordLinkRow.user_id == current_user.id,
            UserRecordLinkRow.patient_passport_id == patient_id,
        )
        .order_by(MedicalRecordRow.event_date.desc(), MedicalRecordRow.created_at.desc()),
    ).all()

    summaries: list[PatientRecordSummaryResponseSchema] = []
    for record_id in record_ids:
        accessible_record = repository.get_accessible_record(
            record_id=record_id,
            user_id=current_user.id,
        )
        if accessible_record is None:
            continue
        summaries.append(_to_record_summary(accessible_record))
    return summaries


def _accessible_patient_passports_query(
    current_user: AuthenticatedUserDTO,
) -> Select[tuple[PatientPassportRow]]:
    if current_user.role == 'patient':
        return (
            select(PatientPassportRow)
            .outerjoin(UserRecordLinkRow, UserRecordLinkRow.patient_passport_id == PatientPassportRow.id)
            .where(
                or_(
                    PatientPassportRow.patient_user_id == current_user.id,
                    UserRecordLinkRow.user_id == current_user.id,
                ),
            )
            .distinct()
            .order_by(PatientPassportRow.confirmed_at.desc().nullslast(), PatientPassportRow.created_at.desc())
        )

    return (
        select(PatientPassportRow)
        .outerjoin(UserRecordLinkRow, UserRecordLinkRow.patient_passport_id == PatientPassportRow.id)
        .where(
            or_(
                PatientPassportRow.created_by_user_id == current_user.id,
                UserRecordLinkRow.user_id == current_user.id,
            ),
        )
        .distinct()
        .order_by(PatientPassportRow.updated_at.desc())
    )


def _get_accessible_patient_passport(
    patient_id: UUID,
    current_user: AuthenticatedUserDTO,
    session: Session,
) -> PatientPassportRow | None:
    return session.scalar(
        _accessible_patient_passports_query(current_user).where(PatientPassportRow.id == patient_id),
    )


def _to_patient_summary(
    row: PatientPassportRow,
    current_user: AuthenticatedUserDTO,
    session: Session,
) -> PatientSummaryResponseSchema:
    record_count, last_record_date = _patient_record_stats(row.id, current_user, session)
    return PatientSummaryResponseSchema(
        id=row.id,
        fio=row.fio,
        date_of_birth=row.date_of_birth,
        email=row.email,
        phone=row.phone,
        status=row.status.value,
        record_count=record_count,
        last_record_date=last_record_date,
    )


def _patient_record_stats(
    patient_id: UUID,
    current_user: AuthenticatedUserDTO,
    session: Session,
) -> tuple[int, date | None]:
    stats = session.execute(
        select(
            func.count(func.distinct(UserRecordLinkRow.record_id)),
            func.max(MedicalRecordRow.event_date),
        )
        .join(MedicalRecordRow, MedicalRecordRow.id == UserRecordLinkRow.record_id)
        .where(
            UserRecordLinkRow.user_id == current_user.id,
            UserRecordLinkRow.patient_passport_id == patient_id,
        ),
    ).one()
    return int(stats[0] or 0), stats[1]


def _to_record_summary(
    accessible_record: AccessibleMedicalRecordDTO,
) -> PatientRecordSummaryResponseSchema:
    record_dto = _to_medical_record_dto(accessible_record)
    return PatientRecordSummaryResponseSchema(
        id=record_dto.id,
        status=record_dto.status,
        record_type=record_dto.record_type,
        event_date=record_dto.event_date,
        title=record_dto.title,
        appointment_location=record_dto.appointment_location,
        clinical_summary=record_dto.clinical_summary,
        author_practitioner_passport=_to_practitioner_response(record_dto.author_practitioner_passport),
        comments_count=record_dto.comments_count,
        attachments_count=record_dto.attachments_count,
        created_at=record_dto.created_at,
        updated_at=record_dto.updated_at,
    )


def _to_practitioner_response(
    practitioner: PractitionerPassportDTO | None,
) -> PractitionerPassportResponseSchema | None:
    if practitioner is None:
        return None
    return PractitionerPassportResponseSchema.model_validate(practitioner)

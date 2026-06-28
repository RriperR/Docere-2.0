"""REST-роуты заявок пациентов на роль врача."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.ports.repositories.doctor_role_applications.dtos import (
    DoctorRoleApplicationDTO,
    DoctorRoleReviewerCandidateDTO,
)
from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.doctor_role_applications.errors import (
    DoctorRoleApplicationAccessDeniedError,
    DoctorRoleApplicationConflictError,
    DoctorRoleApplicationNotFoundError,
    DoctorRoleApplicationValidationError,
)
from app.application.use_cases.doctor_role_applications.use_cases import (
    CreateDoctorRoleApplicationUseCase,
    ListDoctorRoleApplicationInboxUseCase,
    ListDoctorRoleApplicationsUseCase,
    ListDoctorRoleReviewersUseCase,
    ListDoctorSpecialtiesUseCase,
    ReviewDoctorRoleApplicationUseCase,
)
from app.infrastructure.adapters.repositories.audit_events import AuditEventRepositoryAdapter
from app.infrastructure.adapters.repositories.doctor_role_applications import (
    SqlAlchemyDoctorRoleApplicationRepositoryAdapter,
)
from app.presentation.rest.public.v1.auth.dependencies import db_session_dependency
from app.presentation.rest.public.v1.doctor_role_applications.schemas import (
    CreateDoctorRoleApplicationSchema,
    DoctorRoleApplicationResponseSchema,
    DoctorRoleReviewerCandidateSchema,
    ReviewDoctorRoleApplicationSchema,
)
from app.presentation.rest.public.v1.records.dependencies import current_authenticated_user_dependency
from app.presentation.webserver.http_errors import raise_forbidden, raise_not_found

router = APIRouter(prefix='/doctor-role-applications', tags=['doctor-role-applications'])


def _repository(session: Session) -> SqlAlchemyDoctorRoleApplicationRepositoryAdapter:
    return SqlAlchemyDoctorRoleApplicationRepositoryAdapter(session=session)


def get_list_specialties_use_case(session: Session = db_session_dependency) -> ListDoctorSpecialtiesUseCase:
    """Собрать use case списка специализаций.

    Returns:
        Настроенный use case.
    """
    return ListDoctorSpecialtiesUseCase(repository=_repository(session))


def get_list_reviewers_use_case(session: Session = db_session_dependency) -> ListDoctorRoleReviewersUseCase:
    """Собрать use case списка проверяющих.

    Returns:
        Настроенный use case.
    """
    return ListDoctorRoleReviewersUseCase(repository=_repository(session))


def get_create_application_use_case(session: Session = db_session_dependency) -> CreateDoctorRoleApplicationUseCase:
    """Собрать use case создания заявки.

    Returns:
        Настроенный use case.
    """
    return CreateDoctorRoleApplicationUseCase(
        repository=_repository(session),
        audit_events=AuditEventRepositoryAdapter(session=session),
    )


def get_list_applications_use_case(session: Session = db_session_dependency) -> ListDoctorRoleApplicationsUseCase:
    """Собрать use case истории заявок.

    Returns:
        Настроенный use case.
    """
    return ListDoctorRoleApplicationsUseCase(repository=_repository(session))


def get_list_inbox_use_case(session: Session = db_session_dependency) -> ListDoctorRoleApplicationInboxUseCase:
    """Собрать use case входящих заявок.

    Returns:
        Настроенный use case.
    """
    return ListDoctorRoleApplicationInboxUseCase(repository=_repository(session))


def get_review_application_use_case(session: Session = db_session_dependency) -> ReviewDoctorRoleApplicationUseCase:
    """Собрать use case решения по заявке.

    Returns:
        Настроенный use case.
    """
    return ReviewDoctorRoleApplicationUseCase(
        repository=_repository(session),
        audit_events=AuditEventRepositoryAdapter(session=session),
    )


list_specialties_use_case_dependency = Depends(get_list_specialties_use_case)
list_reviewers_use_case_dependency = Depends(get_list_reviewers_use_case)
create_application_use_case_dependency = Depends(get_create_application_use_case)
list_applications_use_case_dependency = Depends(get_list_applications_use_case)
list_inbox_use_case_dependency = Depends(get_list_inbox_use_case)
review_application_use_case_dependency = Depends(get_review_application_use_case)


@router.get('/specialties', response_model=list[str])
def list_doctor_specialties(
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ListDoctorSpecialtiesUseCase = list_specialties_use_case_dependency,
) -> tuple[str, ...]:
    """Вернуть пациенту доступные специализации.

    Returns:
        Доступные специализации подтвержденных врачей.
    """
    try:
        return use_case.execute(actor_role=current_user.role)
    except DoctorRoleApplicationAccessDeniedError:
        raise_forbidden('Only patients can choose a doctor specialty')


@router.get('/reviewers', response_model=list[DoctorRoleReviewerCandidateSchema])
def list_doctor_role_reviewers(
    specialty: str = Query(min_length=2, max_length=255),
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ListDoctorRoleReviewersUseCase = list_reviewers_use_case_dependency,
) -> tuple[DoctorRoleReviewerCandidateDTO, ...]:
    """Вернуть пациенту подходящих проверяющих.

    Returns:
        Активные администраторы и врачи выбранной специализации.

    Raises:
        HTTPException: Если специализация некорректна.
    """
    try:
        return use_case.execute(
            actor_user_id=current_user.id,
            actor_role=current_user.role,
            specialty=specialty,
        )
    except DoctorRoleApplicationAccessDeniedError:
        raise_forbidden('Only patients can choose reviewers')
    except DoctorRoleApplicationValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid specialty') from exc


@router.post('', response_model=DoctorRoleApplicationResponseSchema, status_code=status.HTTP_201_CREATED)
def create_doctor_role_application(
    payload: CreateDoctorRoleApplicationSchema,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: CreateDoctorRoleApplicationUseCase = create_application_use_case_dependency,
    session: Session = db_session_dependency,
) -> DoctorRoleApplicationDTO:
    """Создать заявку с выбранными пациентом проверяющими.

    Returns:
        Созданная заявка.

    Raises:
        HTTPException: Если есть активная заявка или проверяющие не дают кворум.
    """
    try:
        application = use_case.execute(
            actor_user_id=current_user.id,
            actor_role=current_user.role,
            specialty=payload.specialty,
            reviewer_user_ids=tuple(payload.reviewer_user_ids),
        )
        session.commit()
        return application
    except DoctorRoleApplicationAccessDeniedError:
        session.rollback()
        raise_forbidden('Only patients can request doctor role')
    except DoctorRoleApplicationConflictError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Pending doctor role application already exists',
        ) from exc
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Pending doctor role application already exists',
        ) from exc
    except DoctorRoleApplicationValidationError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Choose an admin or at least two doctors of the selected specialty',
        ) from exc
    except Exception:
        session.rollback()
        raise


@router.get('/mine', response_model=list[DoctorRoleApplicationResponseSchema])
def list_my_doctor_role_applications(
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ListDoctorRoleApplicationsUseCase = list_applications_use_case_dependency,
) -> tuple[DoctorRoleApplicationDTO, ...]:
    """Вернуть историю заявок текущего пользователя.

    Returns:
        Заявки пользователя от новых к старым.
    """
    return use_case.execute(actor_user_id=current_user.id)


@router.get('/inbox', response_model=list[DoctorRoleApplicationResponseSchema])
def list_doctor_role_application_inbox(
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ListDoctorRoleApplicationInboxUseCase = list_inbox_use_case_dependency,
) -> tuple[DoctorRoleApplicationDTO, ...]:
    """Вернуть назначенные врачу или администратору заявки.

    Returns:
        Pending-заявки текущего проверяющего.
    """
    try:
        return use_case.execute(actor_user_id=current_user.id, actor_role=current_user.role)
    except DoctorRoleApplicationAccessDeniedError:
        raise_forbidden('Only doctors and admins can review doctor role applications')


@router.post('/{application_id}/review', response_model=DoctorRoleApplicationResponseSchema)
def review_doctor_role_application(
    application_id: UUID,
    payload: ReviewDoctorRoleApplicationSchema,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ReviewDoctorRoleApplicationUseCase = review_application_use_case_dependency,
    session: Session = db_session_dependency,
) -> DoctorRoleApplicationDTO:
    """Сохранить решение выбранного проверяющего и пересчитать кворум.

    Returns:
        Заявка с актуальным прогрессом и итоговым статусом.

    Raises:
        HTTPException: Если заявка уже рассмотрена или решение некорректно.
    """
    try:
        application = use_case.execute(
            application_id=application_id,
            actor_user_id=current_user.id,
            actor_role=current_user.role,
            decision=payload.decision,
            note=payload.note,
        )
        session.commit()
        return application
    except DoctorRoleApplicationAccessDeniedError:
        session.rollback()
        raise_forbidden('Only assigned doctors or admins can review this application')
    except DoctorRoleApplicationNotFoundError:
        session.rollback()
        raise_not_found('Doctor role application not found')
    except DoctorRoleApplicationConflictError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Application is already reviewed') from exc
    except DoctorRoleApplicationValidationError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid review decision') from exc
    except Exception:
        session.rollback()
        raise

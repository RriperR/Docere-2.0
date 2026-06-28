"""REST-роуты администрирования пользователей."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.use_cases.admin_dashboard.get_summary import (
    AdminDashboardAccessDeniedError,
    GetAdminDashboardSummaryUseCase,
)
from app.application.use_cases.audit_events.list_audit_events import (
    AuditEventAccessDeniedError,
    ListAuditEventsUseCase,
)
from app.application.use_cases.auth.change_user_status.use_case import (
    ChangeUserStatusAccessDeniedError,
    ChangeUserStatusNotFoundError,
    ChangeUserStatusSelfBlockError,
    ChangeUserStatusUseCase,
    ChangeUserStatusValidationError,
)
from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.auth.create_staff_user.use_case import (
    CreateStaffUserUseCase,
    StaffUserAccessDeniedError,
    StaffUserValidationError,
)
from app.application.use_cases.auth.errors import EmailAlreadyExistsError
from app.application.use_cases.auth.list_users.use_case import ListUsersAccessDeniedError, ListUsersUseCase
from app.infrastructure.adapters.repositories.admin_dashboard import SqlAlchemyAdminDashboardRepositoryAdapter
from app.infrastructure.adapters.repositories.audit_events import AuditEventRepositoryAdapter
from app.infrastructure.adapters.repositories.auth.sqlalchemy_auth_repository import SqlAlchemyAuthRepositoryAdapter
from app.infrastructure.adapters.security.pbkdf2_password_hasher import Pbkdf2PasswordHasherAdapter
from app.presentation.rest.public.v1.admin.schemas import (
    AdminDashboardSummaryResponseSchema,
    AdminUserResponseSchema,
    AuditEventResponseSchema,
    ChangeUserStatusRequestSchema,
    CreateStaffUserRequestSchema,
)
from app.presentation.rest.public.v1.auth.dependencies import db_session_dependency
from app.presentation.rest.public.v1.auth.schemas import AuthUserResponseSchema
from app.presentation.rest.public.v1.records.dependencies import current_authenticated_user_dependency
from app.presentation.webserver.http_errors import raise_email_already_exists, raise_forbidden, raise_not_found

router = APIRouter(prefix='/admin', tags=['admin'])


def get_admin_dashboard_summary_use_case(
    session: Session = db_session_dependency,
) -> GetAdminDashboardSummaryUseCase:
    """Создать use case административной сводки.

    Returns:
        Настроенный use case административной сводки.
    """
    return GetAdminDashboardSummaryUseCase(
        repository=SqlAlchemyAdminDashboardRepositoryAdapter(session=session),
    )


admin_dashboard_summary_use_case_dependency = Depends(get_admin_dashboard_summary_use_case)


def get_create_staff_user_use_case(session: Session = db_session_dependency) -> CreateStaffUserUseCase:
    """Создать use case создания staff-пользователя.

    Args:
        session: Активная сессия БД.

    Returns:
        Настроенный use case.
    """
    return CreateStaffUserUseCase(
        repository=SqlAlchemyAuthRepositoryAdapter(session=session),
        password_hasher=Pbkdf2PasswordHasherAdapter(),
    )


create_staff_user_use_case_dependency = Depends(get_create_staff_user_use_case)


def get_list_users_use_case(session: Session = db_session_dependency) -> ListUsersUseCase:
    """Создать use case просмотра пользователей.

    Args:
        session: Активная сессия БД.

    Returns:
        Настроенный use case.
    """
    return ListUsersUseCase(repository=SqlAlchemyAuthRepositoryAdapter(session=session))


list_users_use_case_dependency = Depends(get_list_users_use_case)


def get_change_user_status_use_case(session: Session = db_session_dependency) -> ChangeUserStatusUseCase:
    """Создать use case изменения статуса пользователя.

    Returns:
        Настроенный use case изменения статуса пользователя.
    """
    return ChangeUserStatusUseCase(
        repository=SqlAlchemyAuthRepositoryAdapter(session=session),
        audit_events=AuditEventRepositoryAdapter(session=session),
    )


change_user_status_use_case_dependency = Depends(get_change_user_status_use_case)


def get_list_audit_events_use_case(session: Session = db_session_dependency) -> ListAuditEventsUseCase:
    """Создать use case просмотра audit log.

    Args:
        session: Активная сессия БД.

    Returns:
        Настроенный use case.
    """
    return ListAuditEventsUseCase(repository=AuditEventRepositoryAdapter(session=session))


list_audit_events_use_case_dependency = Depends(get_list_audit_events_use_case)


@router.get('/summary', response_model=AdminDashboardSummaryResponseSchema)
def get_admin_dashboard_summary(
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: GetAdminDashboardSummaryUseCase = admin_dashboard_summary_use_case_dependency,
) -> AdminDashboardSummaryResponseSchema:
    """Вернуть административную оперативную сводку.

    Returns:
        Актуальные счетчики пользователей, архивов и sharing.
    """
    try:
        summary = use_case.execute(actor_role=current_user.role)
    except AdminDashboardAccessDeniedError:
        raise_forbidden('Only admin can view dashboard summary')
    return AdminDashboardSummaryResponseSchema.model_validate(summary, from_attributes=True)


@router.get('/users', response_model=list[AdminUserResponseSchema])
def list_users(
    limit: int = Query(default=200, ge=1, le=500),
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ListUsersUseCase = list_users_use_case_dependency,
) -> tuple[AdminUserResponseSchema, ...]:
    """Вернуть пользователей для административной панели.

    Args:
        limit: Максимальное количество пользователей.
        current_user: Текущий аутентифицированный пользователь.
        use_case: Use case просмотра пользователей.

    Returns:
        Пользователи в административной проекции.
    """
    try:
        users = use_case.execute(actor_role=current_user.role, limit=limit)
    except ListUsersAccessDeniedError:
        raise_forbidden('Only admin can view users')
    return tuple(AdminUserResponseSchema.model_validate(user, from_attributes=True) for user in users)


@router.post('/users', response_model=AuthUserResponseSchema, status_code=status.HTTP_201_CREATED)
def create_staff_user(
    payload: CreateStaffUserRequestSchema,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: CreateStaffUserUseCase = create_staff_user_use_case_dependency,
    session: Session = db_session_dependency,
) -> AuthenticatedUserDTO:
    """Создать врача или администратора.

    Args:
        payload: Тело запроса создания пользователя.
        current_user: Текущий аутентифицированный пользователь.
        use_case: Use case создания staff-пользователя.
        session: Активная сессия БД.

    Returns:
        Профиль созданного пользователя.

    Raises:
        HTTPException: Если роль недопустима или БД вернула непредусмотренную ошибку целостности.
        IntegrityError: Если ошибка целостности не связана с duplicate email.
    """
    try:
        created_user = use_case.execute(
            actor_role=current_user.role,
            fio=payload.fio,
            email=str(payload.email).lower(),
            phone=payload.phone,
            password=payload.password,
            role=payload.role,
        )
        session.commit()
        return created_user
    except StaffUserAccessDeniedError:
        session.rollback()
        raise_forbidden('Only admin can create staff users')
    except StaffUserValidationError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid staff role') from exc
    except EmailAlreadyExistsError:
        session.rollback()
        raise_email_already_exists()
    except IntegrityError as error:
        session.rollback()
        error_text = str(error.orig).lower()
        if 'users.email' in error_text or 'unique constraint failed: users.email' in error_text:
            raise_email_already_exists()
        raise
    except Exception:
        session.rollback()
        raise


@router.patch('/users/{user_id}/status', response_model=AdminUserResponseSchema)
def change_user_status(
    user_id: UUID,
    payload: ChangeUserStatusRequestSchema,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ChangeUserStatusUseCase = change_user_status_use_case_dependency,
    session: Session = db_session_dependency,
) -> AdminUserResponseSchema:
    """Заблокировать или разблокировать учетную запись пользователя.

    Returns:
        Пользователь с актуальным статусом.

    Raises:
        HTTPException: Если действие запрещено или пользователь не найден.
    """
    try:
        result = use_case.execute(
            actor_user_id=current_user.id,
            actor_role=current_user.role,
            target_user_id=user_id,
            target_status=payload.status,
        )
        session.commit()
        return AdminUserResponseSchema.model_validate(result.user, from_attributes=True)
    except ChangeUserStatusAccessDeniedError:
        session.rollback()
        raise_forbidden('Only admin can change user status')
    except ChangeUserStatusSelfBlockError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Admin cannot block own account',
        ) from exc
    except ChangeUserStatusNotFoundError:
        session.rollback()
        raise_not_found('User not found')
    except ChangeUserStatusValidationError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid user status') from exc
    except Exception:
        session.rollback()
        raise


@router.get('/audit-events', response_model=list[AuditEventResponseSchema])
def list_audit_events(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ListAuditEventsUseCase = list_audit_events_use_case_dependency,
) -> tuple[AuditEventResponseSchema, ...]:
    """Вернуть последние события audit log.

    Args:
        limit: Максимальное количество событий.
        current_user: Текущий аутентифицированный пользователь.
        use_case: Use case просмотра audit log.

    Returns:
        Последние события audit log.
    """
    try:
        events = use_case.execute(actor_role=current_user.role, limit=limit)
    except AuditEventAccessDeniedError:
        raise_forbidden('Only admin can view audit events')
    return tuple(AuditEventResponseSchema.model_validate(event, from_attributes=True) for event in events)

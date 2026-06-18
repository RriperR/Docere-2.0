"""REST-роуты администрирования пользователей."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.auth.create_staff_user.use_case import (
    CreateStaffUserUseCase,
    StaffUserAccessDeniedError,
    StaffUserValidationError,
)
from app.application.use_cases.auth.errors import EmailAlreadyExistsError
from app.infrastructure.adapters.repositories.auth.sqlalchemy_auth_repository import SqlAlchemyAuthRepositoryAdapter
from app.infrastructure.adapters.security.pbkdf2_password_hasher import Pbkdf2PasswordHasherAdapter
from app.presentation.rest.public.v1.admin.schemas import CreateStaffUserRequestSchema
from app.presentation.rest.public.v1.auth.dependencies import db_session_dependency
from app.presentation.rest.public.v1.auth.schemas import AuthUserResponseSchema
from app.presentation.rest.public.v1.records.dependencies import current_authenticated_user_dependency
from app.presentation.webserver.http_errors import raise_email_already_exists, raise_forbidden

router = APIRouter(prefix='/admin', tags=['admin'])


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

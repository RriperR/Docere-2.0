"""REST-роуты аутентификации пользователя."""

from __future__ import annotations

import logging

from fastapi import APIRouter, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO, AuthTokenDTO
from app.application.use_cases.auth.errors import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    InvalidTokenError,
    UserNotFoundError,
)
from app.application.use_cases.auth.get_authenticated_user.use_case import GetAuthenticatedUserUseCase
from app.application.use_cases.auth.login_user.use_case import LoginUserUseCase
from app.application.use_cases.auth.refresh_access_token.use_case import RefreshAccessTokenUseCase
from app.application.use_cases.auth.register_user.use_case import RegisterUserUseCase
from app.infrastructure.adapters.repositories.audit_events import AuditEventRepositoryAdapter
from app.infrastructure.adapters.repositories.auth.sqlalchemy_auth_repository import SqlAlchemyAuthRepositoryAdapter
from app.presentation.rest.public.v1.auth.dependencies import (
    authenticated_user_use_case_dependency,
    bearer_token_extraction_dependency,
    db_session_dependency,
    login_user_dependency,
    refresh_access_token_dependency,
    register_user_dependency,
)
from app.presentation.rest.public.v1.auth.schemas import (
    AuthTokenResponseSchema,
    AuthUserResponseSchema,
    LoginRequestSchema,
    RefreshTokenRequestSchema,
    RegisterUserRequestSchema,
)
from app.presentation.webserver.http_errors import (
    raise_email_already_exists,
    raise_invalid_credentials,
    raise_unauthorized,
)
from app.presentation.webserver.rate_limit import check_auth_rate_limit

router = APIRouter(prefix='/auth', tags=['auth'])
logger = logging.getLogger(__name__)


def _is_duplicate_user_email_error(error: IntegrityError) -> bool:
    """Проверить, что ошибка БД связана с уникальностью email пользователя.

    Returns:
        `True`, если ошибка соответствует нарушению уникальности `users.email`.
    """
    error_text = str(error.orig).lower()
    return 'users.email' in error_text or 'unique constraint failed: users.email' in error_text


@router.post(
    '/register',
    response_model=AuthUserResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    payload: RegisterUserRequestSchema,
    use_case: RegisterUserUseCase = register_user_dependency,
    session: Session = db_session_dependency,
) -> AuthenticatedUserDTO:
    """Зарегистрировать нового пользователя.

    Args:
        payload: Тело запроса регистрации.
        use_case: Use case регистрации пациента.
        session: Активная сессия БД для транзакции регистрации.

    Returns:
        Данные созданного пользователя.

    Raises:
        IntegrityError: Если БД вернула непредусмотренную ошибку целостности.
    """
    normalized_email = str(payload.email).lower()
    check_auth_rate_limit(f'register:{normalized_email}')
    try:
        with session.begin():
            return use_case.execute(
                fio=payload.fio,
                email=normalized_email,
                phone=payload.phone,
                password=payload.password,
                date_of_birth=payload.date_of_birth,
            )
    except EmailAlreadyExistsError:
        raise_email_already_exists()
    except IntegrityError as error:
        if _is_duplicate_user_email_error(error):
            raise_email_already_exists()
        raise


@router.post('/login', response_model=AuthTokenResponseSchema)
def login(
    payload: LoginRequestSchema,
    use_case: LoginUserUseCase = login_user_dependency,
    session: Session = db_session_dependency,
) -> AuthTokenDTO:
    """Выполнить вход пользователя.

    Args:
        payload: Тело запроса входа.
        use_case: Use case аутентификации.
        session: Активная сессия БД для записи аудита.

    Returns:
        Пара access- и refresh-токенов.
    """
    normalized_email = str(payload.email).lower()
    check_auth_rate_limit(f'login:{normalized_email}')
    try:
        token = use_case.execute(email=normalized_email, password=payload.password)
        try:
            current_user = SqlAlchemyAuthRepositoryAdapter(session=session).find_by_email(email=normalized_email)
            if current_user is not None:
                AuditEventRepositoryAdapter(session).record(
                    actor_user_id=current_user.id,
                    event_type='login',
                    entity_type='user',
                    entity_id=current_user.id,
                    metadata_json={'email': normalized_email},
                )
                session.commit()
        except SQLAlchemyError:
            session.rollback()
            logger.warning('Failed to record login audit event', exc_info=True)
        return token
    except InvalidCredentialsError:
        session.rollback()
        raise_invalid_credentials()


@router.post('/refresh', response_model=AuthTokenResponseSchema)
def refresh_tokens(
    payload: RefreshTokenRequestSchema,
    use_case: RefreshAccessTokenUseCase = refresh_access_token_dependency,
) -> AuthTokenDTO:
    """Обновить пару access/refresh токенов.

    Args:
        payload: Тело запроса с refresh-токеном.
        use_case: Use case обновления токенов.

    Returns:
        Новая пара access- и refresh-токенов.
    """
    try:
        return use_case.execute(refresh_token=payload.refresh_token)
    except InvalidRefreshTokenError:
        raise_unauthorized('Invalid or expired refresh token')


@router.get('/me', response_model=AuthUserResponseSchema)
def get_authenticated_user(
    token: str = bearer_token_extraction_dependency,
    use_case: GetAuthenticatedUserUseCase = authenticated_user_use_case_dependency,
) -> AuthenticatedUserDTO:
    """Вернуть профиль текущего пользователя по токену.

    Args:
        token: Bearer-токен пользователя.
        use_case: Use case получения пользователя.

    Returns:
        Публичные данные текущего пользователя.
    """
    try:
        return use_case.execute(token=token)
    except (InvalidTokenError, UserNotFoundError):
        raise_unauthorized('Invalid or expired token')

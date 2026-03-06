"""Dependency-фабрики для auth-эндпоинтов."""

from __future__ import annotations

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.use_cases.get_authenticated_user import GetAuthenticatedUser
from app.application.use_cases.login_user import LoginUser
from app.application.use_cases.refresh_access_token import RefreshAccessToken
from app.application.use_cases.register_patient_user import RegisterPatientUser
from app.infrastructure.db.session import get_db_session
from app.infrastructure.repositories.auth_repository import SqlAlchemyAuthRepository
from app.infrastructure.security.password_hasher import Pbkdf2PasswordHasher
from app.infrastructure.security.token_service import JwtTokenService
from app.infrastructure.settings import get_settings
from app.presentation.webserver.http_errors import raise_unauthorized

bearer_scheme = HTTPBearer(auto_error=False)
db_session_dependency = Depends(get_db_session)
bearer_token_dependency = Security(bearer_scheme)


def _build_token_service() -> JwtTokenService:
    settings = get_settings()
    return JwtTokenService(
        secret_key=settings.auth.secret_key.get_secret_value(),
        access_ttl_minutes=settings.auth.access_token_ttl_minutes,
        refresh_ttl_minutes=settings.auth.refresh_token_ttl_minutes,
        algorithm=settings.auth.jwt_algorithm,
    )


def extract_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = bearer_token_dependency,
) -> str:
    """Извлечь Bearer-токен из заголовка Authorization.

    Args:
        credentials: Данные HTTP Bearer авторизации.

    Returns:
        Непустой строковый токен.
    """
    if credentials is None:
        raise_unauthorized('Authentication required')

    if credentials.scheme.lower() != 'bearer':
        raise_unauthorized('Invalid authentication scheme')

    token = credentials.credentials.strip()
    if not token:
        raise_unauthorized('Authentication required')
    return token


def get_register_patient_user(
    session: Session = db_session_dependency,
) -> RegisterPatientUser:
    """Создать use-case регистрации пациента.

    Args:
        session: Активная сессия БД.

    Returns:
        Экземпляр `RegisterPatientUser`.
    """
    return RegisterPatientUser(
        repository=SqlAlchemyAuthRepository(session=session),
        password_hasher=Pbkdf2PasswordHasher(),
    )


def get_login_user(
    session: Session = db_session_dependency,
) -> LoginUser:
    """Создать use-case входа пользователя.

    Args:
        session: Активная сессия БД.

    Returns:
        Экземпляр `LoginUser`.
    """
    return LoginUser(
        repository=SqlAlchemyAuthRepository(session=session),
        password_hasher=Pbkdf2PasswordHasher(),
        token_service=_build_token_service(),
    )


def get_authenticated_user_use_case(
    session: Session = db_session_dependency,
) -> GetAuthenticatedUser:
    """Создать use-case получения текущего пользователя.

    Args:
        session: Активная сессия БД.

    Returns:
        Экземпляр `GetAuthenticatedUser`.
    """
    return GetAuthenticatedUser(
        repository=SqlAlchemyAuthRepository(session=session),
        token_service=_build_token_service(),
    )


def get_refresh_access_token_use_case(
    session: Session = db_session_dependency,
) -> RefreshAccessToken:
    """Создать use-case обновления access-токена.

    Args:
        session: Активная сессия БД.

    Returns:
        Экземпляр `RefreshAccessToken`.
    """
    return RefreshAccessToken(
        repository=SqlAlchemyAuthRepository(session=session),
        token_service=_build_token_service(),
    )

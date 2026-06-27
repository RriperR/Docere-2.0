"""Dependency-фабрики для auth-эндпоинтов."""

from __future__ import annotations

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.use_cases.auth.change_password.use_case import ChangePasswordUseCase
from app.application.use_cases.auth.get_authenticated_user.use_case import GetAuthenticatedUserUseCase
from app.application.use_cases.auth.login_user.use_case import LoginUserUseCase
from app.application.use_cases.auth.refresh_access_token.use_case import RefreshAccessTokenUseCase
from app.application.use_cases.auth.register_user.use_case import RegisterUserUseCase
from app.infrastructure.adapters.repositories.auth.sqlalchemy_auth_repository import SqlAlchemyAuthRepositoryAdapter
from app.infrastructure.adapters.repositories.patient_passports.sqlalchemy_patient_passport_repository import (
    SqlAlchemyPatientPassportRepositoryAdapter,
)
from app.infrastructure.adapters.security.jwt_token_service import JwtTokenServiceAdapter
from app.infrastructure.adapters.security.pbkdf2_password_hasher import Pbkdf2PasswordHasherAdapter
from app.infrastructure.config.settings import get_settings
from app.infrastructure.db.session import get_db_session
from app.presentation.webserver.http_errors import raise_unauthorized

bearer_scheme = HTTPBearer(auto_error=False)
db_session_dependency = Depends(get_db_session)
bearer_token_dependency = Security(bearer_scheme)


def _build_token_service() -> JwtTokenServiceAdapter:
    settings = get_settings()
    return JwtTokenServiceAdapter(
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


def get_register_user(
    session: Session = db_session_dependency,
) -> RegisterUserUseCase:
    """Создать use case регистрации пациента.

    Args:
        session: Активная сессия БД.

    Returns:
        Экземпляр `RegisterUserUseCase`.
    """
    return RegisterUserUseCase(
        repository=SqlAlchemyAuthRepositoryAdapter(session=session),
        patient_passport_repository=SqlAlchemyPatientPassportRepositoryAdapter(session=session),
        password_hasher=Pbkdf2PasswordHasherAdapter(),
    )


def get_login_user(
    session: Session = db_session_dependency,
) -> LoginUserUseCase:
    """Создать use case входа пользователя.

    Args:
        session: Активная сессия БД.

    Returns:
        Экземпляр `LoginUserUseCase`.
    """
    return LoginUserUseCase(
        repository=SqlAlchemyAuthRepositoryAdapter(session=session),
        password_hasher=Pbkdf2PasswordHasherAdapter(),
        token_service=_build_token_service(),
    )


def get_authenticated_user_use_case(
    session: Session = db_session_dependency,
) -> GetAuthenticatedUserUseCase:
    """Создать use case получения текущего пользователя.

    Args:
        session: Активная сессия БД.

    Returns:
        Экземпляр `GetAuthenticatedUserUseCase`.
    """
    return GetAuthenticatedUserUseCase(
        repository=SqlAlchemyAuthRepositoryAdapter(session=session),
        token_service=_build_token_service(),
    )


def get_refresh_access_token_use_case(
    session: Session = db_session_dependency,
) -> RefreshAccessTokenUseCase:
    """Создать use case обновления access-токена.

    Args:
        session: Активная сессия БД.

    Returns:
        Экземпляр `RefreshAccessTokenUseCase`.
    """
    return RefreshAccessTokenUseCase(
        repository=SqlAlchemyAuthRepositoryAdapter(session=session),
        token_service=_build_token_service(),
    )


def get_change_password_use_case(
    session: Session = db_session_dependency,
) -> ChangePasswordUseCase:
    """Создать use case смены пароля текущего пользователя.

    Args:
        session: Активная сессия БД.

    Returns:
        Настроенный use case смены пароля.
    """
    return ChangePasswordUseCase(
        repository=SqlAlchemyAuthRepositoryAdapter(session=session),
        password_hasher=Pbkdf2PasswordHasherAdapter(),
    )


register_user_dependency = Depends(get_register_user)
login_user_dependency = Depends(get_login_user)
refresh_access_token_dependency = Depends(get_refresh_access_token_use_case)
authenticated_user_use_case_dependency = Depends(get_authenticated_user_use_case)
change_password_use_case_dependency = Depends(get_change_password_use_case)
bearer_token_extraction_dependency = Depends(extract_bearer_token)

"""Dependency-фабрики для REST-эндпоинтов медицинских записей."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.dto.auth_user_view import AuthUserView
from app.application.use_cases.auth_errors import InvalidTokenError, UserNotFoundError
from app.application.use_cases.create_medical_record import CreateMedicalRecord
from app.application.use_cases.get_authenticated_user import GetAuthenticatedUser
from app.application.use_cases.get_medical_record import GetMedicalRecord
from app.infrastructure.db.session import get_db_session
from app.infrastructure.repositories.medical_record_repository import SqlAlchemyMedicalRecordRepository
from app.presentation.rest.auth.dependencies import (
    authenticated_user_use_case_dependency,
    bearer_token_extraction_dependency,
)
from app.presentation.webserver.http_errors import raise_unauthorized

db_session_dependency = Depends(get_db_session)


def get_current_authenticated_user(
    token: str = bearer_token_extraction_dependency,
    use_case: GetAuthenticatedUser = authenticated_user_use_case_dependency,
) -> AuthUserView:
    """Получить текущего аутентифицированного пользователя.

    Args:
        token: Bearer-токен текущего пользователя.
        use_case: Use-case получения пользователя по токену.

    Returns:
        DTO текущего пользователя.
    """
    try:
        return use_case.execute(token=token)
    except (InvalidTokenError, UserNotFoundError):
        raise_unauthorized('Invalid or expired token')


def get_create_medical_record_use_case(
    session: Session = db_session_dependency,
) -> CreateMedicalRecord:
    """Создать use-case создания медицинской записи.

    Args:
        session: Активная сессия БД.

    Returns:
        Экземпляр `CreateMedicalRecord`.
    """
    return CreateMedicalRecord(repository=SqlAlchemyMedicalRecordRepository(session=session))


def get_medical_record_use_case(
    session: Session = db_session_dependency,
) -> GetMedicalRecord:
    """Создать use-case получения медицинской записи.

    Args:
        session: Активная сессия БД.

    Returns:
        Экземпляр `GetMedicalRecord`.
    """
    return GetMedicalRecord(repository=SqlAlchemyMedicalRecordRepository(session=session))


current_authenticated_user_dependency = Depends(get_current_authenticated_user)
create_medical_record_use_case_dependency = Depends(get_create_medical_record_use_case)
get_medical_record_use_case_dependency = Depends(get_medical_record_use_case)

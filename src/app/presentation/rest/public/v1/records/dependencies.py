"""Dependency-фабрики REST-эндпоинтов медицинских записей."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.auth.errors import InvalidTokenError, UserNotFoundError
from app.application.use_cases.auth.get_authenticated_user.use_case import GetAuthenticatedUserUseCase
from app.application.use_cases.medical_records.add_record_comment.use_case import AddRecordCommentUseCase
from app.application.use_cases.medical_records.create_medical_record.use_case import CreateMedicalRecordUseCase
from app.application.use_cases.medical_records.get_medical_record.use_case import GetMedicalRecordUseCase
from app.infrastructure.adapters.repositories.medical_records.sqlalchemy_medical_record_repository import (
    SqlAlchemyMedicalRecordRepositoryAdapter,
)
from app.infrastructure.db.session import get_db_session
from app.presentation.rest.public.v1.auth.dependencies import (
    authenticated_user_use_case_dependency,
    bearer_token_extraction_dependency,
)
from app.presentation.webserver.http_errors import raise_unauthorized

db_session_dependency = Depends(get_db_session)


def get_current_authenticated_user(
    token: str = bearer_token_extraction_dependency,
    use_case: GetAuthenticatedUserUseCase = authenticated_user_use_case_dependency,
) -> AuthenticatedUserDTO:
    """Получить текущего аутентифицированного пользователя по bearer-токену.

    Returns:
        DTO текущего пользователя.
    """
    try:
        return use_case.execute(token=token)
    except (InvalidTokenError, UserNotFoundError):
        raise_unauthorized('Invalid or expired token')


def _build_repository(session: Session) -> SqlAlchemyMedicalRecordRepositoryAdapter:
    return SqlAlchemyMedicalRecordRepositoryAdapter(session=session)


def get_create_medical_record_use_case(
    session: Session = db_session_dependency,
) -> CreateMedicalRecordUseCase:
    """Создать use case создания медицинской записи.

    Returns:
        Настроенный use case создания записи.
    """
    return CreateMedicalRecordUseCase(repository=_build_repository(session))


def get_medical_record_use_case(
    session: Session = db_session_dependency,
) -> GetMedicalRecordUseCase:
    """Создать use case чтения медицинской записи.

    Returns:
        Настроенный use case чтения записи.
    """
    return GetMedicalRecordUseCase(repository=_build_repository(session))


def get_add_record_comment_use_case(
    session: Session = db_session_dependency,
) -> AddRecordCommentUseCase:
    """Создать use case добавления комментария к записи.

    Returns:
        Настроенный use case создания комментария.
    """
    return AddRecordCommentUseCase(repository=_build_repository(session))


current_authenticated_user_dependency = Depends(get_current_authenticated_user)
create_medical_record_use_case_dependency = Depends(get_create_medical_record_use_case)
get_medical_record_use_case_dependency = Depends(get_medical_record_use_case)
add_record_comment_use_case_dependency = Depends(get_add_record_comment_use_case)

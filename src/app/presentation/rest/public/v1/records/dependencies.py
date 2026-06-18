"""Dependency-фабрики REST-эндпоинтов медицинских записей."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.auth.errors import InvalidTokenError, UserNotFoundError
from app.application.use_cases.auth.get_authenticated_user.use_case import GetAuthenticatedUserUseCase
from app.application.use_cases.medical_records.add_record_comment.use_case import AddRecordCommentUseCase
from app.application.use_cases.medical_records.comment_attachments.use_cases import (
    AddCommentAttachmentUseCase,
    DownloadAttachmentUseCase,
)
from app.application.use_cases.medical_records.create_medical_record.use_case import CreateMedicalRecordUseCase
from app.application.use_cases.medical_records.get_medical_record.use_case import GetMedicalRecordUseCase
from app.application.use_cases.medical_records.record_attachments.use_cases import AddRecordAttachmentUseCase
from app.application.use_cases.patients.create_patient import CreatePatientUseCase
from app.application.use_cases.patients.get_patient import GetPatientUseCase
from app.application.use_cases.patients.list_patient_records import ListPatientRecordsUseCase
from app.application.use_cases.patients.list_patients import ListPatientsUseCase
from app.application.use_cases.patients.search_patients import SearchPatientsUseCase
from app.application.use_cases.share_requests.use_cases import (
    AcceptShareRequestUseCase,
    CancelShareRequestUseCase,
    CreateShareRequestUseCase,
    DeclineShareRequestUseCase,
    ListInboxShareRequestsUseCase,
    ListOutboxShareRequestsUseCase,
    RevokeShareRequestUseCase,
)
from app.infrastructure.adapters.repositories.medical_records.sqlalchemy_medical_record_repository import (
    SqlAlchemyMedicalRecordRepositoryAdapter,
)
from app.infrastructure.adapters.repositories.patient_cards.sqlalchemy_patient_card_repository import (
    SqlAlchemyPatientCardRepositoryAdapter,
)
from app.infrastructure.adapters.repositories.share_requests.sqlalchemy_share_request_repository import (
    SqlAlchemyShareRequestRepositoryAdapter,
)
from app.infrastructure.adapters.storage.factory import get_file_storage
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


def _build_patient_card_repository(session: Session) -> SqlAlchemyPatientCardRepositoryAdapter:
    return SqlAlchemyPatientCardRepositoryAdapter(session=session)


def _build_share_request_repository(session: Session) -> SqlAlchemyShareRequestRepositoryAdapter:
    return SqlAlchemyShareRequestRepositoryAdapter(session=session)


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


def get_add_comment_attachment_use_case(
    session: Session = db_session_dependency,
) -> AddCommentAttachmentUseCase:
    """Создать use case загрузки вложения к комментарию.

    Returns:
        Настроенный use case загрузки вложения.
    """
    return AddCommentAttachmentUseCase(repository=_build_repository(session), storage=get_file_storage())


def get_download_attachment_use_case(
    session: Session = db_session_dependency,
) -> DownloadAttachmentUseCase:
    """Создать use case скачивания вложения.

    Returns:
        Настроенный use case скачивания вложения.
    """
    return DownloadAttachmentUseCase(repository=_build_repository(session), storage=get_file_storage())


def get_add_record_attachment_use_case(
    session: Session = db_session_dependency,
) -> AddRecordAttachmentUseCase:
    """Создать use case загрузки вложения к записи.

    Returns:
        Настроенный use case загрузки вложения к записи.
    """
    return AddRecordAttachmentUseCase(repository=_build_repository(session), storage=get_file_storage())


def get_list_patients_use_case(session: Session = db_session_dependency) -> ListPatientsUseCase:
    """Создать use case получения списка карточек пациентов.

    Returns:
        Настроенный use case списка карточек пациентов.
    """
    return ListPatientsUseCase(repository=_build_patient_card_repository(session))


def get_create_patient_use_case(session: Session = db_session_dependency) -> CreatePatientUseCase:
    """Создать use case создания карточки пациента.

    Returns:
        Настроенный use case создания карточки пациента.
    """
    return CreatePatientUseCase(repository=_build_patient_card_repository(session))


def get_get_patient_use_case(session: Session = db_session_dependency) -> GetPatientUseCase:
    """Создать use case чтения карточки пациента.

    Returns:
        Настроенный use case чтения карточки пациента.
    """
    return GetPatientUseCase(repository=_build_patient_card_repository(session))


def get_list_patient_records_use_case(session: Session = db_session_dependency) -> ListPatientRecordsUseCase:
    """Создать use case списка записей карточки пациента.

    Returns:
        Настроенный use case списка записей карточки.
    """
    return ListPatientRecordsUseCase(repository=_build_patient_card_repository(session))


def get_search_patients_use_case(session: Session = db_session_dependency) -> SearchPatientsUseCase:
    """Создать use case fuzzy-поиска карточек пациентов.

    Returns:
        Настроенный use case поиска карточек пациентов.
    """
    return SearchPatientsUseCase(repository=_build_patient_card_repository(session))


def get_create_share_request_use_case(session: Session = db_session_dependency) -> CreateShareRequestUseCase:
    """Создать use case создания sharing-запроса.

    Returns:
        Настроенный use case создания sharing-запроса.
    """
    return CreateShareRequestUseCase(repository=_build_share_request_repository(session))


def get_list_inbox_share_requests_use_case(session: Session = db_session_dependency) -> ListInboxShareRequestsUseCase:
    """Создать use case входящих sharing-запросов.

    Returns:
        Настроенный use case входящих sharing-запросов.
    """
    return ListInboxShareRequestsUseCase(repository=_build_share_request_repository(session))


def get_list_outbox_share_requests_use_case(session: Session = db_session_dependency) -> ListOutboxShareRequestsUseCase:
    """Создать use case исходящих sharing-запросов.

    Returns:
        Настроенный use case исходящих sharing-запросов.
    """
    return ListOutboxShareRequestsUseCase(repository=_build_share_request_repository(session))


def get_accept_share_request_use_case(session: Session = db_session_dependency) -> AcceptShareRequestUseCase:
    """Создать use case принятия sharing-запроса.

    Returns:
        Настроенный use case принятия sharing-запроса.
    """
    return AcceptShareRequestUseCase(repository=_build_share_request_repository(session))


def get_decline_share_request_use_case(session: Session = db_session_dependency) -> DeclineShareRequestUseCase:
    """Создать use case отклонения sharing-запроса.

    Returns:
        Настроенный use case отклонения sharing-запроса.
    """
    return DeclineShareRequestUseCase(repository=_build_share_request_repository(session))


def get_cancel_share_request_use_case(session: Session = db_session_dependency) -> CancelShareRequestUseCase:
    """Создать use case отмены sharing-запроса.

    Returns:
        Настроенный use case отмены sharing-запроса.
    """
    return CancelShareRequestUseCase(repository=_build_share_request_repository(session))


def get_revoke_share_request_use_case(session: Session = db_session_dependency) -> RevokeShareRequestUseCase:
    """Создать use case отзыва sharing-запроса.

    Returns:
        Настроенный use case отзыва sharing-запроса.
    """
    return RevokeShareRequestUseCase(repository=_build_share_request_repository(session))


current_authenticated_user_dependency = Depends(get_current_authenticated_user)
create_medical_record_use_case_dependency = Depends(get_create_medical_record_use_case)
get_medical_record_use_case_dependency = Depends(get_medical_record_use_case)
add_record_comment_use_case_dependency = Depends(get_add_record_comment_use_case)
add_comment_attachment_use_case_dependency = Depends(get_add_comment_attachment_use_case)
add_record_attachment_use_case_dependency = Depends(get_add_record_attachment_use_case)
download_attachment_use_case_dependency = Depends(get_download_attachment_use_case)
list_patients_use_case_dependency = Depends(get_list_patients_use_case)
create_patient_use_case_dependency = Depends(get_create_patient_use_case)
get_patient_use_case_dependency = Depends(get_get_patient_use_case)
list_patient_records_use_case_dependency = Depends(get_list_patient_records_use_case)
search_patients_use_case_dependency = Depends(get_search_patients_use_case)
create_share_request_use_case_dependency = Depends(get_create_share_request_use_case)
list_inbox_share_requests_use_case_dependency = Depends(get_list_inbox_share_requests_use_case)
list_outbox_share_requests_use_case_dependency = Depends(get_list_outbox_share_requests_use_case)
accept_share_request_use_case_dependency = Depends(get_accept_share_request_use_case)
decline_share_request_use_case_dependency = Depends(get_decline_share_request_use_case)
cancel_share_request_use_case_dependency = Depends(get_cancel_share_request_use_case)
revoke_share_request_use_case_dependency = Depends(get_revoke_share_request_use_case)

"""Поиск материалов и авторизованный просмотр документов клинического случая."""

from datetime import date
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.application.case_materials import MaterialFilters
from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.clinical_cases import ClinicalCasesUseCase
from app.application.use_cases.medical_records.comment_attachments.dtos import DownloadAttachmentDTO
from app.application.use_cases.medical_records.comment_attachments.use_cases import DownloadAttachmentUseCase
from app.application.use_cases.medical_records.common.dtos import MedicalRecordDTO
from app.application.use_cases.medical_records.errors import FileAttachmentNotFoundError, MedicalRecordAccessDeniedError
from app.domain.clinical_cases import CaseMessage
from app.presentation.rest.public.v1.cases.dependencies import case_transaction, cases_dependency
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
    download_attachment_use_case_dependency,
)

router = APIRouter()
query_parameter = Query(default='', max_length=200)
offset_parameter = Query(default=0, ge=0)
limit_parameter = Query(default=20, ge=1, le=100)


@router.get('/{case_id}/materials')
def materials(
    case_id: UUID,
    query: str = query_parameter,
    record_type: Literal['consultation_result', 'exam_result', 'lab_result', 'other'] | None = None,
    status: Literal['confirmed', 'unconfirmed'] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    offset: int = offset_parameter,
    limit: int = limit_parameter,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> dict[str, object]:
    """Найти страницу материалов по метаданным без чтения PDF или сканов.

    Args:
        case_id: Идентификатор случая.
        query: Поисковая строка.
        record_type: Параметр операции.
        status: Параметр операции.
        date_from: Параметр операции.
        date_to: Параметр операции.
        offset: Число пропускаемых элементов.
        limit: Размер страницы.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.materials(
            case_id, actor.id, MaterialFilters(query, record_type, status, date_from, date_to), offset, limit
        )


@router.get('/{case_id}/materials/{record_id}')
def material_details(
    case_id: UUID,
    record_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> MedicalRecordDTO:
    """Прочитать выбранную запись только при полном доступе к случаю.

    Args:
        case_id: Идентификатор случая.
        record_id: Ссылка на выбранный материал.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.material_details(case_id, actor.id, record_id)


@router.get('/{case_id}/materials/{record_id}/attachments/{attachment_id}')
def attachment(
    case_id: UUID,
    record_id: UUID,
    attachment_id: UUID,
    download: bool = False,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
    downloader: DownloadAttachmentUseCase = download_attachment_use_case_dependency,
) -> Response:
    """Отдать файл без публичной ссылки на хранилище, с повторной проверкой ACL.

    Args:
        case_id: Идентификатор случая.
        record_id: Ссылка на выбранный материал.
        attachment_id: Вложение указанного материала.
        download: Параметр операции.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.
        downloader: Параметр операции.

    Returns:
        Результат сценария в контексте текущего пользователя.

    Raises:
        HTTPException: При нарушении условий операции.
    """
    with case_transaction(session):
        uc.authorize_attachment(case_id, actor.id, record_id, attachment_id)
        try:
            result = downloader.execute(DownloadAttachmentDTO(attachment_id, actor.id, record_id))
        except FileAttachmentNotFoundError as exc:
            raise HTTPException(404, 'Вложение не найдено') from exc
        except MedicalRecordAccessDeniedError as exc:
            raise HTTPException(403, 'Вложение недоступно') from exc
        signatures = {'application/pdf': b'%PDF-', 'image/png': b'\x89PNG\r\n\x1a\n', 'image/jpeg': b'\xff\xd8\xff'}
        previewable = result.mime_type in signatures and result.content.startswith(signatures[result.mime_type])
        disposition = 'inline' if previewable and not download else 'attachment'
        return Response(
            result.content,
            media_type=result.mime_type if previewable else 'application/octet-stream',
            headers={
                'Content-Disposition': f"{disposition}; filename*=UTF-8''{quote(result.filename)}",
                'Cache-Control': 'private, no-store',
                'X-Content-Type-Options': 'nosniff',
            },
        )


@router.get('/{case_id}/messages/{message_id}')
def message(
    case_id: UUID,
    message_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: ClinicalCasesUseCase = cases_dependency,
    session: Session = db_session_dependency,
) -> CaseMessage:
    """Открыть исходное сообщение из ответа или уведомления.

    Args:
        case_id: Идентификатор случая.
        message_id: Параметр операции.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.get_message(case_id, actor.id, message_id)

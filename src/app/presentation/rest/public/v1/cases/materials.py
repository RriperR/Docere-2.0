"""Поиск материалов и авторизованный просмотр документов клинического случая."""

from datetime import date
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.clinical_cases.dtos import (
    MaterialFilters,
    MaterialSummary,
    PageDTO,
)
from app.application.use_cases.clinical_cases.materials import CaseMaterialsUseCase
from app.application.use_cases.medical_records.comment_attachments.dtos import DownloadAttachmentDTO
from app.application.use_cases.medical_records.comment_attachments.use_cases import DownloadAttachmentUseCase
from app.application.use_cases.medical_records.common.dtos import MedicalRecordDTO
from app.application.use_cases.medical_records.errors import FileAttachmentNotFoundError, MedicalRecordAccessDeniedError
from app.presentation.rest.public.v1.cases.dependencies import case_transaction, materials_dependency
from app.presentation.rest.public.v1.cases.responses import (
    MaterialResponse,
    PageResponse,
)
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
    download_attachment_use_case_dependency,
)
from app.presentation.rest.public.v1.records.schemas import MedicalRecordResponseSchema

router = APIRouter()
query_parameter = Query(default='', max_length=200)
offset_parameter = Query(default=0, ge=0)
limit_parameter = Query(default=20, ge=1, le=100)


@router.get('/{case_id}/materials', response_model=PageResponse[MaterialResponse])
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
    uc: CaseMaterialsUseCase = materials_dependency,
    session: Session = db_session_dependency,
) -> PageDTO[MaterialSummary]:
    """Найти страницу материалов по метаданным без чтения PDF или сканов.

    Args:
        case_id: Идентификатор клинического случая.
        query: Текст для поиска по разрешённым полям.
        record_type: Тип медицинской записи для фильтрации.
        status: Состояние случая для фильтрации.
        date_from: Нижняя включительная граница даты медицинского события.
        date_to: Верхняя включительная граница даты медицинского события.
        offset: Число элементов, пропускаемых перед страницей.
        limit: Максимальное число элементов страницы.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Страница найденных материалов без чтения содержимого PDF и сканов.
    """
    with case_transaction(session):
        return uc.materials(
            case_id, actor.id, MaterialFilters(query, record_type, status, date_from, date_to), offset, limit
        )


@router.get('/{case_id}/materials/{record_id}', response_model=MedicalRecordResponseSchema)
def material_details(
    case_id: UUID,
    record_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseMaterialsUseCase = materials_dependency,
    session: Session = db_session_dependency,
) -> MedicalRecordDTO:
    """Прочитать выбранную запись только при полном доступе к случаю.

    Args:
        case_id: Идентификатор клинического случая.
        record_id: Идентификатор записи, включённой в материалы случая.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Доступная медицинская запись с её вложениями и комментариями.
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
    uc: CaseMaterialsUseCase = materials_dependency,
    session: Session = db_session_dependency,
    downloader: DownloadAttachmentUseCase = download_attachment_use_case_dependency,
) -> Response:
    """Отдать файл без публичной ссылки на хранилище, с повторной проверкой ACL.

    Args:
        case_id: Идентификатор клинического случая.
        record_id: Идентификатор записи, включённой в материалы случая.
        attachment_id: Вложение указанной медицинской записи.
        download: Выдать файл как скачивание, даже если формат поддерживает просмотр.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.
        downloader: Сценарий загрузки содержимого вложения из закрытого хранилища.

    Returns:
        Содержимое файла с безопасным MIME, заголовком скачивания/просмотра и запретом кэширования.

    Raises:
        HTTPException: Если доступ запрещён, ссылка недействительна или возник конфликт изменения.
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


@router.get('/patients/{patient_id}/available-records', response_model=PageResponse[MaterialResponse])
def available_records(
    patient_id: UUID,
    query: str = query_parameter,
    offset: int = offset_parameter,
    limit: int = limit_parameter,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseMaterialsUseCase = materials_dependency,
    session: Session = db_session_dependency,
) -> PageDTO[MaterialSummary]:
    """Выбрать страницу собственных доступных записей для нового разбора.

    Args:
        patient_id: Идентификатор конкретного паспорта пациента.
        query: Текст для поиска по разрешённым полям.
        offset: Число элементов, пропускаемых перед страницей.
        limit: Максимальное число элементов страницы.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Страница записей пациента, которые текущий врач может включить в разбор.
    """
    with case_transaction(session):
        return uc.available_materials(patient_id, actor.id, query, offset, limit)

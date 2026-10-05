"""Защищённое HTTP API совместных клинических разборов."""

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.clinical_cases.conclusions import CaseConclusionsUseCase
from app.application.use_cases.clinical_cases.dtos import (
    CaseView,
    ClosurePreview,
    PageDTO,
    PublicationPreview,
    PublicationResult,
)
from app.application.use_cases.medical_records.create_medical_record.use_case import CreateMedicalRecordUseCase
from app.domain.clinical_cases import CaseConclusion
from app.presentation.rest.public.v1.cases.dependencies import case_transaction, conclusions_dependency
from app.presentation.rest.public.v1.cases.responses import (
    CaseViewResponse,
    ClosurePreviewResponse,
    ConclusionResponse,
    PageResponse,
    PublicationPreviewResponse,
    PublicationResponse,
)
from app.presentation.rest.public.v1.cases.schemas import (
    CloseSchema,
    ConclusionSchema,
    PublishSchema,
)
from app.presentation.rest.public.v1.records.dependencies import (
    create_medical_record_use_case_dependency,
    current_authenticated_user_dependency,
    db_session_dependency,
)

router = APIRouter()
offset_query = Query(default=0, ge=0)
limit_query = Query(default=20, ge=1, le=100)
optional_query = Query(default='', max_length=200)


@router.get('/{case_id}/conclusions', response_model=PageResponse[ConclusionResponse])
def conclusions(
    case_id: UUID,
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseConclusionsUseCase = conclusions_dependency,
    session: Session = db_session_dependency,
) -> PageDTO[CaseConclusion]:
    """Получить версии итога с пагинацией.

    Args:
        case_id: Идентификатор клинического случая.
        offset: Число элементов, пропускаемых перед страницей.
        limit: Максимальное число элементов страницы.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Версии итога, начиная с последней, и их общее число.
    """
    with case_transaction(session):
        return uc.list_conclusions(case_id, actor.id, offset, limit)


@router.post('/{case_id}/conclusions', status_code=201, response_model=ConclusionResponse)
def save_conclusion(
    case_id: UUID,
    payload: ConclusionSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseConclusionsUseCase = conclusions_dependency,
    session: Session = db_session_dependency,
) -> CaseConclusion:
    """Сохранить новую неизменяемую версию итога.

    Args:
        case_id: Идентификатор клинического случая.
        payload: Проверенное тело HTTP-запроса.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Новая неизменяемая версия итога координатора.
    """
    with case_transaction(session):
        return uc.save_conclusion(
            case_id,
            actor.id,
            payload.version,
            payload.summary,
            payload.findings,
            payload.next_actions,
            payload.source_ids,
        )


@router.get('/{case_id}/closure-preview', response_model=ClosurePreviewResponse)
def closure_preview(
    case_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseConclusionsUseCase = conclusions_dependency,
    session: Session = db_session_dependency,
) -> ClosurePreview:
    """Проверить открытые запросы перед завершением.

    Args:
        case_id: Идентификатор клинического случая.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Число открытых запросов и версия случая перед подтверждением закрытия.
    """
    with case_transaction(session):
        return uc.closure_preview(case_id, actor.id)


@router.post('/{case_id}/close', response_model=CaseViewResponse)
def close_case(
    case_id: UUID,
    payload: CloseSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseConclusionsUseCase = conclusions_dependency,
    session: Session = db_session_dependency,
) -> CaseView:
    """Завершить разбор, сохранив участникам доступ для чтения.

    Args:
        case_id: Идентификатор клинического случая.
        payload: Проверенное тело HTTP-запроса.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Безопасная карточка случая после изменения; клинический контекст скрывается при потере доступа.
    """
    with case_transaction(session):
        return uc.close(case_id, actor.id, payload.version, payload.cancel_open_requests)


@router.get('/{case_id}/publication-preview', response_model=PublicationPreviewResponse)
def publication_preview(
    case_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseConclusionsUseCase = conclusions_dependency,
    session: Session = db_session_dependency,
) -> PublicationPreview:
    """Показать предпросмотр самостоятельной медицинской записи.

    Args:
        case_id: Идентификатор клинического случая.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Текст будущей записи, версия итога, источники и существующая публикация, если она есть.
    """
    with case_transaction(session):
        return uc.publication_preview(case_id, actor.id)


@router.post('/{case_id}/publish', response_model=PublicationResponse)
def publish(
    case_id: UUID,
    payload: PublishSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseConclusionsUseCase = conclusions_dependency,
    session: Session = db_session_dependency,
    creator: CreateMedicalRecordUseCase = create_medical_record_use_case_dependency,
) -> PublicationResult:
    """Опубликовать итог с датой события через существующий сценарий записи.

    Args:
        case_id: Идентификатор клинического случая.
        payload: Проверенное тело HTTP-запроса.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.
        creator: Существующий сценарий создания медицинской записи в той же транзакции.

    Returns:
        Идентификатор самостоятельной записи; created=False при повторной публикации.
    """
    with case_transaction(session):
        return uc.publish(case_id, actor, payload.event_date, creator)

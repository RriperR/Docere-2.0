"""Защищённое HTTP API совместных клинических разборов."""

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.clinical_cases.discussion import CaseDiscussionUseCase
from app.application.use_cases.clinical_cases.dtos import CaseActivityEntry, DiscussionPage, PageDTO
from app.domain.clinical_cases import CaseMessage, OpinionRequest
from app.presentation.rest.public.v1.cases.dependencies import case_transaction, discussion_dependency
from app.presentation.rest.public.v1.cases.responses import (
    ActivityResponse,
    DiscussionResponse,
    MessageResponse,
    OpinionResponse,
    PageResponse,
)
from app.presentation.rest.public.v1.cases.schemas import (
    DiscussionReadSchema,
    MessageSchema,
    OpinionSchema,
)
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
)

router = APIRouter()
offset_query = Query(default=0, ge=0)
limit_query = Query(default=20, ge=1, le=100)
optional_query = Query(default='', max_length=200)


@router.get('/{case_id}/messages', response_model=DiscussionResponse)
def get_messages(
    case_id: UUID,
    query: str = optional_query,
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseDiscussionUseCase = discussion_dependency,
    session: Session = db_session_dependency,
) -> DiscussionPage:
    """Прочитать страницу защищённого обсуждения.

    Args:
        case_id: Идентификатор клинического случая.
        query: Текст для поиска по разрешённым полям.
        offset: Число элементов, пропускаемых перед страницей.
        limit: Максимальное число элементов страницы.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Страница сообщений и последовательность событий доступного случая.
    """
    with case_transaction(session):
        return uc.discussion(case_id, actor.id, offset, limit, query)


@router.post('/{case_id}/messages', status_code=201, response_model=MessageResponse)
def send_message(
    case_id: UUID,
    payload: MessageSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseDiscussionUseCase = discussion_dependency,
    session: Session = db_session_dependency,
) -> CaseMessage:
    """Отправить реплику или ответ адресному запросу идемпотентно.

    Args:
        case_id: Идентификатор клинического случая.
        payload: Проверенное тело HTTP-запроса.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Новая реплика либо ранее созданный результат запроса с тем же ключом.
    """
    with case_transaction(session):
        return uc.send_message(
            case_id,
            actor.id,
            payload.body,
            payload.idempotency_key,
            payload.parent_id,
            payload.record_id,
            payload.attachment_id,
            payload.opinion_id,
        )


@router.get('/{case_id}/opinions', response_model=PageResponse[OpinionResponse])
def get_opinions(
    case_id: UUID,
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseDiscussionUseCase = discussion_dependency,
    session: Session = db_session_dependency,
) -> PageDTO[OpinionRequest]:
    """Прочитать страницу адресных запросов.

    Args:
        case_id: Идентификатор клинического случая.
        offset: Число элементов, пропускаемых перед страницей.
        limit: Максимальное число элементов страницы.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Страница адресных запросов мнения.
    """
    with case_transaction(session):
        return uc.list_opinions(case_id, actor.id, offset, limit)


@router.post('/{case_id}/opinions', status_code=201, response_model=OpinionResponse)
def request_opinion(
    case_id: UUID,
    payload: OpinionSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseDiscussionUseCase = discussion_dependency,
    session: Session = db_session_dependency,
) -> OpinionRequest:
    """Запросить мнение другого участника.

    Args:
        case_id: Идентификатор клинического случая.
        payload: Проверенное тело HTTP-запроса.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Созданный открытый запрос назначенному участнику.
    """
    with case_transaction(session):
        return uc.request_opinion(case_id, actor.id, payload.assignee_id, payload.question, payload.record_id)


@router.post('/{case_id}/opinions/{opinion_id}/cancel', response_model=OpinionResponse)
def cancel_opinion(
    case_id: UUID,
    opinion_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseDiscussionUseCase = discussion_dependency,
    session: Session = db_session_dependency,
) -> OpinionRequest:
    """Отменить запрос автором или координатором.

    Args:
        case_id: Идентификатор клинического случая.
        opinion_id: Идентификатор адресного запроса мнения.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Отменённый запрос с зафиксированной причиной.
    """
    with case_transaction(session):
        return uc.cancel_opinion(case_id, actor.id, opinion_id)


@router.get('/{case_id}/activity', response_model=PageResponse[ActivityResponse])
def get_activity(
    case_id: UUID,
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseDiscussionUseCase = discussion_dependency,
    session: Session = db_session_dependency,
) -> PageDTO[CaseActivityEntry]:
    """Прочитать страницу журнала действий.

    Args:
        case_id: Идентификатор клинического случая.
        offset: Число элементов, пропускаемых перед страницей.
        limit: Максимальное число элементов страницы.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Страница журнала действий с авторами и ссылками.
    """
    with case_transaction(session):
        return uc.activity(case_id, actor.id, offset, limit)


@router.post('/{case_id}/discussion/read')
def mark_read(
    case_id: UUID,
    payload: DiscussionReadSchema,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseDiscussionUseCase = discussion_dependency,
    session: Session = db_session_dependency,
) -> dict[str, bool]:
    """Отметить просмотренную позицию обсуждения монотонно.

    Args:
        case_id: Идентификатор клинического случая.
        payload: Проверенное тело HTTP-запроса.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Подтверждение отметки обсуждения прочитанным.
    """
    with case_transaction(session):
        uc.mark_read(case_id, actor.id, payload.sequence)
        return {'read': True}


@router.get('/{case_id}/messages/{message_id}', response_model=MessageResponse)
def message(
    case_id: UUID,
    message_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseDiscussionUseCase = discussion_dependency,
    session: Session = db_session_dependency,
) -> CaseMessage:
    """Открыть исходное сообщение из ответа или уведомления.

    Args:
        case_id: Идентификатор клинического случая.
        message_id: Идентификатор реплики в обсуждении случая.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Реплика по идентификатору либо None; проверка контекста выполняется в use case.
    """
    with case_transaction(session):
        return uc.get_message(case_id, actor.id, message_id)


@router.get('/{case_id}/opinions/{opinion_id}', response_model=OpinionResponse)
def opinion(
    case_id: UUID,
    opinion_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: CaseDiscussionUseCase = discussion_dependency,
    session: Session = db_session_dependency,
) -> OpinionRequest:
    """Открыть запрос по защищённой прямой ссылке.

    Args:
        case_id: Случай, которому принадлежит запрос.
        opinion_id: Целевой запрос.
        actor: Аутентифицированный пользователь.
        uc: Прикладной сценарий обсуждения.
        session: Текущая транзакция.

    Returns:
        Запрос после проверки полного доступа.
    """
    with case_transaction(session):
        return uc.get_opinion(case_id, actor.id, opinion_id)

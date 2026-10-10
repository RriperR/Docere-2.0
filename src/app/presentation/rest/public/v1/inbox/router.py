"""Пагинированные входящие; изменение задач остаётся в профильных API."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.clinical_cases.dtos import PageDTO
from app.application.use_cases.inbox.dtos import InboxCounts, InboxTask, TaskKind
from app.application.use_cases.inbox.use_case import InboxUseCase
from app.infrastructure.adapters.repositories.inbox import SqlAlchemyInboxRepository
from app.infrastructure.adapters.repositories.notifications import SqlAlchemyNotificationRepository
from app.presentation.rest.public.v1.cases.dependencies import case_transaction, get_case_context
from app.presentation.rest.public.v1.cases.responses import PageResponse, ResponseSchema
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
)

router = APIRouter(prefix='/inbox', tags=['inbox'])


class InboxTaskResponse(ResponseSchema):
    """Разрешённые метаданные задачи и идентификаторы типизированной цели."""

    key: str
    kind: TaskKind
    id: UUID
    case_id: UUID | None
    actor_name: str | None
    created_at: datetime
    context: str | None


class InboxCountsResponse(ResponseSchema):
    """Раздельные счётчики действий и непрочитанных событий."""

    tasks: int
    by_type: dict[TaskKind, int]
    unread_events: int


def get_inbox(session: Session = db_session_dependency) -> InboxUseCase:
    """Собрать порты очереди и действующую политику доступа.

    Args:
        session: Текущая транзакция.

    Returns:
        Прикладной сценарий входящих.
    """
    return InboxUseCase(
        SqlAlchemyInboxRepository(session), SqlAlchemyNotificationRepository(session), get_case_context(session=session)
    )


inbox_dependency = Depends(get_inbox)
kind_query = Query(default=None)
offset_query = Query(default=0, ge=0)
limit_query = Query(default=20, ge=1, le=100)


@router.get('/tasks', response_model=PageResponse[InboxTaskResponse])
def tasks(
    kind: TaskKind | None = kind_query,
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: InboxUseCase = inbox_dependency,
    session: Session = db_session_dependency,
) -> PageDTO[InboxTask]:
    """Прочитать задачи врача после проверки целей.

    Args:
        kind: Фильтр типа задачи.
        offset: Смещение разрешённых задач.
        limit: Размер страницы.
        actor: Аутентифицированный пользователь.
        uc: Прикладной сценарий.
        session: Текущая транзакция.

    Returns:
        Страница доступных задач.
    """
    with case_transaction(session):
        return uc.tasks(actor.id, kind, offset, limit)


@router.get('/counts', response_model=InboxCountsResponse)
def counts(
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: InboxUseCase = inbox_dependency,
    session: Session = db_session_dependency,
) -> InboxCounts:
    """Получить счётчики актуальных задач и событий.

    Args:
        actor: Аутентифицированный пользователь.
        uc: Прикладной сценарий.
        session: Текущая транзакция.

    Returns:
        Раздельные счётчики с актуальной проверкой доступа.
    """
    with case_transaction(session):
        return uc.counts(actor.id)

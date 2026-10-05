"""Пагинированный центр уведомлений и внутрисистемные задачи врача."""

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from app.application.notifications import NotificationsUseCase
from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.presentation.rest.public.v1.cases.dependencies import case_transaction
from app.presentation.rest.public.v1.notifications.dependencies import notifications_dependency
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
)

router = APIRouter(prefix='/notifications', tags=['notifications'])
offset_query = Query(default=0, ge=0)
limit_query = Query(default=20, ge=1, le=100)


@router.get('')
def notifications(
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: NotificationsUseCase = notifications_dependency,
    session: Session = db_session_dependency,
) -> dict[str, object]:
    """Получить только собственные уведомления с актуальным доступом к цели.

    Args:
        offset: Число пропускаемых элементов.
        limit: Размер страницы.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.list_notifications(actor.id, offset, limit)


@router.get('/count')
def count(
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: NotificationsUseCase = notifications_dependency,
    session: Session = db_session_dependency,
) -> dict[str, object]:
    """Получить собственный счётчик непрочитанного.

    Args:
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.count(actor.id)


@router.get('/attention')
def attention(
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: NotificationsUseCase = notifications_dependency,
    session: Session = db_session_dependency,
) -> dict[str, object]:
    """Показать ожидающие принятия приглашения и ответов запросы.

    Args:
        offset: Число пропускаемых элементов.
        limit: Размер страницы.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        return uc.attention(actor.id, offset, limit)


@router.post('/read-all')
def read_all(
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: NotificationsUseCase = notifications_dependency,
    session: Session = db_session_dependency,
) -> dict[str, bool]:
    """Отметить события прочитанными, не выполняя адресные задачи.

    Args:
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        uc.read(actor.id)
        return {'read': True}


@router.post('/{notification_id}/read')
def read_one(
    notification_id: UUID,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: NotificationsUseCase = notifications_dependency,
    session: Session = db_session_dependency,
) -> dict[str, bool]:
    """Отметить только принадлежащее текущему врачу уведомление.

    Args:
        notification_id: Параметр операции.
        actor: Актуальная учётная запись.
        uc: Прикладной сценарий.
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    with case_transaction(session):
        uc.read(actor.id, notification_id)
        return {'read': True}

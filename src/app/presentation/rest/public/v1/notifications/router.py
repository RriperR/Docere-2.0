"""Пагинированный центр уведомлений и внутрисистемные задачи врача."""

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.clinical_cases.dtos import PageDTO
from app.application.use_cases.notifications.dtos import AttentionView, NotificationCounts, NotificationView
from app.application.use_cases.notifications.use_case import NotificationsUseCase
from app.presentation.rest.public.v1.cases.dependencies import case_transaction
from app.presentation.rest.public.v1.cases.responses import PageResponse
from app.presentation.rest.public.v1.notifications.dependencies import notifications_dependency
from app.presentation.rest.public.v1.notifications.schemas import (
    AttentionResponse,
    NotificationCountResponse,
    NotificationResponse,
)
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
)

router = APIRouter(prefix='/notifications', tags=['notifications'])
offset_query = Query(default=0, ge=0)
limit_query = Query(default=20, ge=1, le=100)


@router.get('', response_model=PageResponse[NotificationResponse])
def notifications(
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: NotificationsUseCase = notifications_dependency,
    session: Session = db_session_dependency,
) -> PageDTO[NotificationView]:
    """Получить только собственные уведомления с актуальным доступом к цели.

    Args:
        offset: Число элементов, пропускаемых перед страницей.
        limit: Максимальное число элементов страницы.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Страница собственных уведомлений с повторно проверенным доступом к цели.
    """
    with case_transaction(session):
        return uc.list_notifications(actor.id, offset, limit)


@router.get('/count', response_model=NotificationCountResponse)
def count(
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: NotificationsUseCase = notifications_dependency,
    session: Session = db_session_dependency,
) -> NotificationCounts:
    """Получить собственный счётчик непрочитанного.

    Args:
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Число непрочитанных уведомлений и версия совокупной активности входящих.
    """
    with case_transaction(session):
        return uc.count(actor.id)


@router.get('/attention', response_model=PageResponse[AttentionResponse])
def attention(
    offset: int = offset_query,
    limit: int = limit_query,
    actor: AuthenticatedUserDTO = current_authenticated_user_dependency,
    uc: NotificationsUseCase = notifications_dependency,
    session: Session = db_session_dependency,
) -> PageDTO[AttentionView]:
    """Показать ожидающие принятия приглашения и ответов запросы.

    Args:
        offset: Число элементов, пропускаемых перед страницей.
        limit: Максимальное число элементов страницы.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Страница приглашений и запросов мнения с актуальной доступностью их целей.
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
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Подтверждение отметки всех своих уведомлений прочитанными.
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
        notification_id: Собственное уведомление; None означает отметить все свои уведомления.
        actor: Аутентифицированный пользователь, выполняющий действие.
        uc: Прикладной сценарий, выполняющий проверку доступа и операцию.
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Подтверждение отметки собственного уведомления прочитанным.
    """
    with case_transaction(session):
        uc.read(actor.id, notification_id)
        return {'read': True}

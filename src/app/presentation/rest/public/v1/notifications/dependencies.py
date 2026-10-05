"""DI центра уведомлений."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.notifications import NotificationsUseCase
from app.infrastructure.adapters.repositories.notifications import SqlAlchemyNotificationRepository
from app.presentation.rest.public.v1.cases.dependencies import get_cases_use_case
from app.presentation.rest.public.v1.records.dependencies import db_session_dependency


def get_notifications_use_case(session: Session = db_session_dependency) -> NotificationsUseCase:
    """Собрать уведомления и проверку прав в одной сессии.

    Args:
        session: Текущая транзакционная сессия.

    Returns:
        Результат сценария в контексте текущего пользователя.
    """
    return NotificationsUseCase(SqlAlchemyNotificationRepository(session), get_cases_use_case(session=session))


notifications_dependency = Depends(get_notifications_use_case)

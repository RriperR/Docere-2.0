"""DI центра уведомлений."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.use_cases.notifications.use_case import NotificationsUseCase
from app.infrastructure.adapters.repositories.notifications import SqlAlchemyNotificationRepository
from app.presentation.rest.public.v1.cases.dependencies import get_case_context
from app.presentation.rest.public.v1.records.dependencies import db_session_dependency


def get_notifications_use_case(session: Session = db_session_dependency) -> NotificationsUseCase:
    """Собрать уведомления и проверку прав в одной сессии.

    Args:
        session: SQLAlchemy-сессия текущей транзакции.

    Returns:
        Прикладная зависимость, использующая репозитории текущей SQLAlchemy-сессии.
    """
    return NotificationsUseCase(SqlAlchemyNotificationRepository(session), get_case_context(session=session))


notifications_dependency = Depends(get_notifications_use_case)

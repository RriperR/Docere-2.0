"""Повторяемая доставка доменного outbox через Celery/Redis."""

from collections.abc import Callable
from datetime import timedelta
from typing import cast, Protocol
from uuid import UUID

import structlog
from sqlalchemy import select

from app.application.use_cases.clinical_cases.context import CaseContext
from app.application.use_cases.clinical_cases.management import ClinicalCasesUseCase
from app.infrastructure.adapters.queue.celery_app import celery_app
from app.infrastructure.adapters.repositories.clinical_cases import SqlAlchemyCaseRepository
from app.infrastructure.adapters.repositories.medical_records.sqlalchemy_medical_record_repository import (
    SqlAlchemyMedicalRecordRepositoryAdapter,
)
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.auth.user import UserRole, UserRow, UserStatus
from app.infrastructure.db.models.clinical_cases import CaseEventRow, CaseNotificationRow
from app.infrastructure.db.session import get_session_factory

logger = structlog.get_logger(__name__)
Task = Callable[[str], None]
task_decorator = cast(
    Callable[[Task], Task],
    celery_app.task(name='docere.case_event', acks_late=True, reject_on_worker_lost=True, ignore_result=True),
)


class _PublishTask(Protocol):
    def apply_async(self, *, args: list[str]) -> object:
        """Передать в брокер только идентификатор доменного события.

        Args:
            args: Идентификатор события в аргументах задачи Celery.
        """
        ...


@task_decorator
def process_case_event(event_id: str) -> None:
    """Доставить уведомления ровно один раз по паре событие/адресат в SQL-транзакции.

    Args:
        event_id: UUID события PostgreSQL outbox в строковом формате.
    """
    with get_session_factory()() as session:
        row = session.scalar(select(CaseEventRow).where(CaseEventRow.id == UUID(event_id)).with_for_update())
        if row is None or row.delivered_at is not None:
            return
        for recipient_id in dict.fromkeys(row.recipients):
            recipient = session.get(UserRow, UUID(recipient_id))
            if (
                recipient is None
                or recipient.id == row.actor_id
                or recipient.role != UserRole.DOCTOR
                or recipient.status != UserStatus.ACTIVE
            ):
                continue
            existing = session.scalar(
                select(CaseNotificationRow.id).where(
                    CaseNotificationRow.event_id == row.id, CaseNotificationRow.recipient_id == recipient.id
                )
            )
            if existing is None:
                session.add(CaseNotificationRow(event_id=row.id, recipient_id=recipient.id))
        row.delivered_at = utc_now()
        session.commit()


def enqueue_case_events(*, limit: int = 100) -> int:
    """Опубликовать намерения; broker outage не отменяет уже сохранённое изменение случая.

    Args:
        limit: Максимальное число событий, передаваемых брокеру за один проход.

    Returns:
        Число событий, успешно переданных брокеру за этот вызов.
    """
    sent = 0
    for _ in range(limit):
        with get_session_factory()() as session:
            row = session.scalar(
                select(CaseEventRow)
                .where(CaseEventRow.delivered_at.is_(None), CaseEventRow.next_attempt_at <= utc_now())
                .order_by(CaseEventRow.next_attempt_at, CaseEventRow.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if row is None:
                break
            try:
                cast(_PublishTask, process_case_event).apply_async(args=[str(row.id)])
                sent += 1
            except Exception:
                logger.warning('case_event_dispatch_retry', event_id=str(row.id))
            row.attempts += 1
            row.next_attempt_at = utc_now() + timedelta(seconds=60)
            session.commit()
    return sent


def cleanup_invalid_participants() -> None:
    """Восстановить инвариант участия после смены роли вне обычного сценария блокировки."""
    with get_session_factory()() as session:
        repository = SqlAlchemyCaseRepository(session)
        uc = ClinicalCasesUseCase(CaseContext(repository, SqlAlchemyMedicalRecordRepositoryAdapter(session)))
        for user_id in repository.inactive_users(50):
            uc.terminate_user(user_id, user_id)
        session.commit()

"""Доставка outbox и восстановление импорта независимо от доступности брокера."""

from __future__ import annotations

import argparse
from datetime import timedelta
from threading import Event
from typing import cast, Protocol

import structlog
from sqlalchemy import or_, select, update

from app.domain.entities.import_job import ImportJobStatus
from app.infrastructure.adapters.queue.case_events import cleanup_invalid_participants, enqueue_case_events
from app.infrastructure.adapters.queue.tasks import process_import_job
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.import_dispatch import ImportDispatchRow
from app.infrastructure.db.models.medical_records.import_job import ImportJobRow
from app.infrastructure.db.session import get_session_factory

logger = structlog.get_logger(__name__)
REDELIVERY_SECONDS = 60


class _CeleryTask(Protocol):
    def apply_async(self, *, args: list[str], kwargs: dict[str, str | None]) -> object:
        """Передать идентификаторы без содержимого медицинского архива.

        Args:
            args: Параметр операции.
            kwargs: Параметр операции.
        """
        ...


def recover_expired_imports() -> None:
    """Вернуть в очередь задания погибших worker после истечения lease."""
    with get_session_factory()() as session:
        recovered = session.scalars(
            update(ImportJobRow)
            .where(
                ImportJobRow.status == ImportJobStatus.RUNNING,
                or_(ImportJobRow.lease_expires_at <= utc_now(), ImportJobRow.lease_expires_at.is_(None)),
            )
            .values(
                status=ImportJobStatus.QUEUED,
                processing_token=None,
                lease_expires_at=None,
                version=ImportJobRow.version + 1,
            )
            .returning(ImportJobRow.id),
        ).all()
        if recovered:
            session.execute(
                update(ImportDispatchRow)
                .where(ImportDispatchRow.job_id.in_(recovered))
                .values(next_attempt_at=utc_now()),
            )
            logger.warning('import_leases_recovered', count=len(recovered))
        session.commit()


def enqueue_recoverable_import_jobs(*, limit: int = 100) -> int:
    """Доставить готовые записи outbox; сбой публикации оставляет намерение в БД.

    Запись остаётся доступной для повторной отправки даже после успешной публикации:
    потеря сообщения брокером до захвата worker не приводит к потере задания.
    Публикация и фиксация БД могут дать дубликат; claim и fencing делают его безопасным.

    Args:
        limit: Максимальное число публикаций за один проход.

    Returns:
        Число подтверждённых публикаций за проход.
    """
    recover_expired_imports()
    sent = 0
    for _ in range(limit):
        with get_session_factory()() as session:
            row = session.scalar(
                select(ImportDispatchRow)
                .join(ImportJobRow, ImportJobRow.id == ImportDispatchRow.job_id)
                .where(ImportJobRow.status == ImportJobStatus.QUEUED, ImportDispatchRow.next_attempt_at <= utc_now())
                .order_by(ImportDispatchRow.next_attempt_at)
                .with_for_update(of=ImportDispatchRow, skip_locked=True)
                .limit(1),
            )
            if row is None:
                break
            try:
                cast(_CeleryTask, process_import_job).apply_async(
                    args=[str(row.job_id)],
                    kwargs={'request_id': row.request_id},
                )
                sent += 1
                logger.info('import_dispatched', job_id=str(row.job_id), request_id=row.request_id)
            except Exception:
                # Не пишем URL брокера, пароль, имена файлов или содержимое архива в лог.
                logger.warning('import_dispatch_retry', job_id=str(row.job_id), request_id=row.request_id)
            row.attempts += 1
            row.next_attempt_at = utc_now() + timedelta(seconds=REDELIVERY_SECONDS)
            session.commit()
    return sent


def main() -> None:
    """Выполнить проход или запустить независимый от Celery цикл доставки."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--loop', action='store_true')
    args = parser.parse_args()
    stop = Event()
    while True:
        try:
            count = enqueue_recoverable_import_jobs()
            logger.info('import_dispatch_cycle', sent=count)
            cleanup_invalid_participants()
            logger.info('case_dispatch_cycle', sent=enqueue_case_events())
        except Exception:
            logger.exception('import_dispatch_cycle_failed')
            if not args.loop:
                raise
        if not args.loop:
            return
        stop.wait(5)


if __name__ == '__main__':
    main()

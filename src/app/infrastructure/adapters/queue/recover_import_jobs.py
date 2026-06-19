"""Восстановление заданий импорта архивов без живой Celery-задачи."""

from __future__ import annotations

from typing import cast, Protocol

from sqlalchemy import select

from app.domain.entities.import_job import ImportJobStatus
from app.infrastructure.adapters.queue.tasks import process_import_job
from app.infrastructure.db.models.medical_records.import_job import ImportJobRow
from app.infrastructure.db.session import get_session_factory


class _CeleryTask(Protocol):
    def delay(self, *args: object, **kwargs: object) -> object:
        """Поставить Celery-задачу в очередь."""
        ...


def enqueue_recoverable_import_jobs(*, limit: int = 1000) -> int:
    """Поставить в очередь задания импорта, оставшиеся во временных статусах.

    Args:
        limit: Максимальное число заданий за один проход восстановления.

    Returns:
        Число поставленных в очередь заданий импорта.
    """
    with get_session_factory()() as session:
        job_ids = session.scalars(
            select(ImportJobRow.id)
            .where(ImportJobRow.status.in_((ImportJobStatus.QUEUED, ImportJobStatus.RUNNING)))
            .order_by(ImportJobRow.created_at.asc())
            .limit(limit),
        ).all()

    task = cast(_CeleryTask, process_import_job)
    for job_id in job_ids:
        task.delay(str(job_id))
    return len(job_ids)


def main() -> None:
    """Выполнить один проход восстановления заданий импорта."""
    count = enqueue_recoverable_import_jobs()
    print(f'Enqueued {count} recoverable import job(s).')


if __name__ == '__main__':
    main()

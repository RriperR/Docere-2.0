"""Фоновые Celery-задачи."""

from collections.abc import Callable
from typing import cast
from uuid import UUID

from app.infrastructure.adapters.queue.celery_app import celery_app
from app.infrastructure.adapters.repositories.import_jobs.sqlalchemy_import_job_repository import (
    SqlAlchemyImportJobRepositoryAdapter,
)
from app.infrastructure.db.session import get_session_factory

TaskCallable = Callable[[], str]
TaskDecorator = Callable[[TaskCallable], TaskCallable]
task_decorator = cast(TaskDecorator, celery_app.task(name='docere.ping'))
ImportTaskCallable = Callable[[str], None]
import_task_decorator = cast(
    Callable[[ImportTaskCallable], ImportTaskCallable], celery_app.task(name='docere.import_job')
)


@task_decorator
def ping() -> str:
    """Проверить доступность воркера.

    Returns:
        Строка `pong`.
    """
    return 'pong'


@import_task_decorator
def process_import_job(job_id: str) -> None:
    """Обработать загруженный архив ImportJob.

    Пока содержимое ZIP не парсится: задача подтверждает, что архив был сохранён,
    и завершает job техническим отчётом.

    Args:
        job_id: Идентификатор ImportJob.
    """
    with get_session_factory()() as session:
        repository = SqlAlchemyImportJobRepositoryAdapter(session=session)
        job = repository.mark_running(job_id=UUID(job_id))
        if job is None:
            return
        repository.mark_completed(
            job_id=job.id,
            report_json={
                'message': 'Archive saved. Domain-specific processing is not implemented yet.',
                'archive_storage_key': job.archive_storage_key,
                'original_filename': job.original_filename,
                'size_bytes': job.size_bytes,
            },
        )
        session.commit()

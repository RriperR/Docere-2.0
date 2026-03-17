"""Фоновые Celery-задачи."""

from collections.abc import Callable
from typing import cast

from app.infrastructure.adapters.queue.celery_app import celery_app

TaskCallable = Callable[[], str]
TaskDecorator = Callable[[TaskCallable], TaskCallable]
task_decorator = cast(TaskDecorator, celery_app.task(name='docere.ping'))


@task_decorator
def ping() -> str:
    """Проверить доступность воркера.

    Returns:
        Строка `pong`.
    """
    return 'pong'

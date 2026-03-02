from collections.abc import Callable
from typing import cast

from app.infrastructure.queue.celery_app import celery_app

TaskCallable = Callable[[], str]
TaskDecorator = Callable[[TaskCallable], TaskCallable]
task_decorator = cast(TaskDecorator, celery_app.task(name='docere.ping'))


@task_decorator
def ping() -> str:
    return 'pong'

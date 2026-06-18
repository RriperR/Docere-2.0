"""Инициализация Celery-приложения."""

from celery import Celery  # type: ignore[import-untyped]

from app.infrastructure.config.settings import get_settings


def create_celery_app() -> Celery:
    """Создать и настроить экземпляр Celery.

    Returns:
        Настроенный Celery-инстанс.
    """
    settings = get_settings()
    app = Celery(
        'docere',
        broker=settings.queue.broker_url,
        backend=settings.queue.result_backend,
        include=['app.infrastructure.adapters.queue.tasks'],
    )
    app.conf.update(
        task_default_queue='docere.default',
        task_ignore_result=False,
        task_publish_retry=False,
        broker_connection_timeout=1,
    )
    return app


celery_app = create_celery_app()

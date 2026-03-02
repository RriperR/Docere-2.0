from celery import Celery  # type: ignore[import-untyped]

from app.infrastructure.settings import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    app = Celery(
        'docere',
        broker=settings.queue.broker_url,
        backend=settings.queue.result_backend,
        include=['app.infrastructure.queue.tasks'],
    )
    app.conf.update(
        task_default_queue='docere.default',
        task_ignore_result=False,
    )
    return app


celery_app = create_celery_app()

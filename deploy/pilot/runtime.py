"""Загрузить файловые secrets и запустить только разрешённый процесс пилота."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote

FORBIDDEN = {'docere', 'minioadmin', 'dev-secret-key', 'change-me-in-production', 'DemoPass123'}


def read_secret(name: str) -> str:
    """Прочитать обязательный secret без включения его значения в ошибку.

    Args:
        name: Имя файла в /run/secrets.

    Returns:
        Значение secret.

    Raises:
        ValueError: Если secret отсутствует, слабый или демонстрационный.
    """
    raw = (Path('/run/secrets') / name).read_text()
    value = raw.strip()
    if name == 'ai_token':
        if not value or '\r' in raw or '\n' in raw:
            raise ValueError('Invalid pilot secret: ai_token')
        return value
    if len(value) < 32 or value in FORBIDDEN or any(char.isspace() for char in value):
        raise ValueError(f'Invalid pilot secret: {name}')
    return value


def configure() -> None:
    """Подготовить настройки приложения из обязательных файловых secrets.

    Raises:
        ValueError: Если AI включён с неполной конфигурацией.
    """
    password = quote(read_secret('postgres_password'), safe='')
    redis_password = quote(read_secret('redis_password'), safe='')
    os.environ['APP_DATABASE__URL'] = f'postgresql+psycopg://docere_pilot:{password}@postgres:5432/docere_pilot'
    os.environ['APP_AUTH__SECRET_KEY'] = read_secret('auth_key')
    os.environ['APP_STORAGE__ACCESS_KEY'] = read_secret('storage_access_key')
    os.environ['APP_STORAGE__SECRET_KEY'] = read_secret('storage_secret_key')
    os.environ['APP_QUEUE__BROKER_URL'] = f'redis://:{redis_password}@redis:6379/0'
    os.environ['APP_QUEUE__RESULT_BACKEND'] = f'redis://:{redis_password}@redis:6379/1'
    if os.environ.get('APP_IMPORT_AI__ENABLED', 'false').lower() == 'true':
        os.environ['APP_IMPORT_AI__TOKEN'] = read_secret('ai_token')
        if not os.environ.get('APP_IMPORT_AI__BASE_URL') or not os.environ.get('APP_IMPORT_AI__MODEL'):
            raise ValueError('AI requires base URL and model')


def main() -> int:
    """Запустить API, worker, dispatcher, migration или bootstrap администратора.

    Returns:
        Код завершения процесса.

    Raises:
        ValueError: Некорректное действие или пароль; перехватывается с кодом 1.
    """
    try:
        configure()
        action = sys.argv[1]
        if action == 'worker-health':
            os.execv(  # noqa: S606 — fixed executable and arguments, no shell
                '/app/.venv/bin/celery',
                [
                    'celery',
                    '-A',
                    'app.infrastructure.adapters.queue.celery_app:celery_app',
                    'inspect',
                    'ping',
                    '-d',
                    f'pilot@{os.environ["HOSTNAME"]}',
                    '--timeout=5',
                ],
            )
        if action == 'worker':
            os.execv(  # noqa: S606 — fixed executable and arguments, no shell
                '/app/.venv/bin/celery',
                [
                    'celery',
                    '-A',
                    'app.infrastructure.adapters.queue.celery_app:celery_app',
                    'worker',
                    '--loglevel=WARNING',
                    '--concurrency=2',
                    '--hostname=pilot@%h',
                ],
            )
        if action == 'dispatcher':
            os.execv(  # noqa: S606 — fixed executable and arguments, no shell
                '/app/.venv/bin/python',
                ['python', '-m', 'app.infrastructure.adapters.queue.recover_import_jobs', '--loop'],
            )
        if action not in {'serve', 'migrate', 'admin'}:
            raise ValueError('Unsupported pilot action')
        # Uvicorn access logs include query strings; nginx also has access_log off.
        from uvicorn.config import LOGGING_CONFIG

        LOGGING_CONFIG['loggers']['uvicorn.access']['handlers'] = []
        LOGGING_CONFIG['loggers']['uvicorn.access']['propagate'] = False
        from app.presentation.cli import main as cli_main

        if action == 'admin':
            # Password arrives through stdin, never as a Docker command argument.
            password = sys.stdin.readline().strip()
            if len(password) < 16 or password in FORBIDDEN:
                raise ValueError('Admin password must contain at least 16 characters')
            return cli_main(['create-admin', '--email', sys.argv[2], '--password', password])
        return cli_main([action])
    except (OSError, ValueError, IndexError):
        print('Pilot startup rejected: check required secrets and configuration.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

"""Критические тесты graceful shutdown HTTP-приложения."""

from __future__ import annotations

import asyncio
import signal
from threading import Thread
from time import sleep
from typing import Any

import pytest
from fastapi import Response
from fastapi.testclient import TestClient
from uvicorn import Config

from app.infrastructure.config.settings import clear_settings_cache
from app.presentation.main import create_app
from app.presentation.webserver.graceful_shutdown import (
    GracefulShutdownController,
    GracefulShutdownServer,
)


async def _dummy_asgi_app(_: Any, __: Any, ___: Any) -> None:
    """Пустое ASGI-приложение для unit-тестов сервера."""


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Подготовить минимальный набор переменных окружения для тестов.

    Args:
        monkeypatch: Инструмент подмены переменных окружения в тесте.
    """
    monkeypatch.setenv('APP_DATABASE__URL', 'sqlite+pysqlite:///./graceful-shutdown-test.sqlite3')
    monkeypatch.setenv('APP_AUTH__SECRET_KEY', 'test-secret-key-32-bytes-minimum-0001')
    monkeypatch.setenv('APP_STORAGE__ENDPOINT', 'http://localhost:9000')
    monkeypatch.setenv('APP_STORAGE__BUCKET', 'docere-records')
    monkeypatch.setenv('APP_QUEUE__BROKER_URL', 'redis://localhost:6379/0')
    monkeypatch.setenv('APP_QUEUE__RESULT_BACKEND', 'redis://localhost:6379/1')


@pytest.mark.critical
def test_new_requests_are_rejected_in_shutdown_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверить отказ новых запросов после перехода в режим shutdown.

    Args:
        monkeypatch: Инструмент подмены переменных окружения в тесте.
    """
    _set_required_env(monkeypatch)
    clear_settings_cache()

    app = create_app(env_file=None)
    controller = app.state.graceful_shutdown_controller

    with TestClient(app) as client:
        controller.begin_shutdown()
        response = client.get('/api/health')

    clear_settings_cache()

    assert response.status_code == 503
    assert response.json()['detail'] == 'Service is shutting down'


@pytest.mark.critical
def test_inflight_request_finishes_while_new_requests_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверить завершение активного запроса во время graceful shutdown.

    Args:
        monkeypatch: Инструмент подмены переменных окружения в тесте.
    """
    _set_required_env(monkeypatch)
    clear_settings_cache()

    app = create_app(env_file=None)
    controller = app.state.graceful_shutdown_controller
    results: dict[str, Any] = {}

    @app.get('/_test/slow')
    def get_slow_response(delay_seconds: float = 0.0) -> Response:
        """Вернуть тестовый ответ после задержки.

        Args:
            delay_seconds: Искусственная задержка ответа.

        Returns:
            Пустой HTTP-ответ со статусом `200 OK`.
        """
        sleep(delay_seconds)
        return Response(status_code=200)

    with TestClient(app) as client:

        def run_slow_request() -> None:
            """Выполнить долгий запрос в отдельном потоке."""
            results['slow_response'] = client.get(
                '/_test/slow',
                params={'delay_seconds': 0.5},
            )

        slow_request_thread = Thread(target=run_slow_request)
        slow_request_thread.start()
        sleep(0.1)

        controller.begin_shutdown()
        rejected_response = client.get('/api/health')

        slow_request_thread.join()

    clear_settings_cache()

    slow_response = results['slow_response']
    assert slow_response.status_code == 200
    assert rejected_response.status_code == 503
    assert rejected_response.json()['detail'] == 'Service is shutting down'


def test_server_delays_transition_to_uvicorn_shutdown() -> None:
    """Проверить отложенный переход сервера к штатному shutdown."""
    controller = GracefulShutdownController()
    server = GracefulShutdownServer(
        Config(app=_dummy_asgi_app),
        reject_window_seconds=0.05,
        controller=controller,
    )
    server.handle_exit(signal.SIGTERM, None)

    assert controller.is_shutting_down is True
    assert server.should_exit is False

    sleep(0.1)

    assert asyncio.run(server.on_tick(1)) is True
    assert server.should_exit is True


def test_server_forces_immediate_shutdown_on_second_signal() -> None:
    """Проверить немедленный штатный shutdown по повторному сигналу."""
    controller = GracefulShutdownController()
    server = GracefulShutdownServer(
        Config(app=_dummy_asgi_app),
        reject_window_seconds=1.0,
        controller=controller,
    )
    server.handle_exit(signal.SIGTERM, None)
    server.handle_exit(signal.SIGTERM, None)

    assert server.should_exit is True

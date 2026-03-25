"""Запуск HTTP-сервера приложения."""

from __future__ import annotations

from uvicorn import Config

from app.infrastructure.config.settings import get_settings
from app.presentation.main import app
from app.presentation.webserver.graceful_shutdown import GracefulShutdownServer

HTTP_HOST = '0.0.0.0'  # noqa: S104
HTTP_PORT = 8000
HTTP_GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS = 10


def run_http_server() -> None:
    """Запустить HTTP-сервер приложения с graceful shutdown."""
    settings = get_settings()
    controller = app.state.graceful_shutdown_controller
    config = Config(
        app=app,
        host=HTTP_HOST,
        port=HTTP_PORT,
        timeout_graceful_shutdown=HTTP_GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS,
    )
    server = GracefulShutdownServer(
        config,
        controller=controller,
        reject_window_seconds=settings.graceful_shutdown_reject_window_seconds,
    )
    server.run()


if __name__ == '__main__':
    run_http_server()

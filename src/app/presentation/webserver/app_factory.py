"""Точка входа FastAPI-приложения."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.infrastructure.config.paths import DEFAULT_ENV_FILE
from app.infrastructure.config.settings import get_settings
from app.infrastructure.db.session import close_db_connections
from app.presentation.router import router as app_router
from app.presentation.webserver.error_handlers import register_error_handlers
from app.presentation.webserver.error_schemas import ErrorResponseSchema
from app.presentation.webserver.graceful_shutdown import GracefulShutdownController

logger = structlog.get_logger(__name__)


def create_app(*, env_file: Path | None = DEFAULT_ENV_FILE) -> FastAPI:
    """Создать и настроить экземпляр FastAPI.

    Args:
        env_file: Путь до dotenv-файла. `None` отключает чтение `.env`.

    Returns:
        Готовое приложение FastAPI.
    """
    controller = GracefulShutdownController()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Проверить настройки на старте приложения и закрыть ресурсы на остановке.

        Args:
            app: Экземпляр FastAPI.

        Yields:
            Управление жизненным циклом FastAPI.
        """
        get_settings(env_file=env_file)
        app.state.graceful_shutdown_controller = controller
        yield
        controller.begin_shutdown()
        close_db_connections()

    app = FastAPI(
        title='Docere Service',
        lifespan=lifespan,
        responses={
            500: {
                'model': ErrorResponseSchema,
                'description': 'Internal server error',
            },
        },
    )
    app.state.graceful_shutdown_controller = controller

    @app.middleware('http')
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Добавить request_id и структурированный HTTP-лог.

        Args:
            request: Входящий HTTP-запрос.
            call_next: Следующий обработчик в middleware-цепочке.

        Returns:
            Ответ приложения с заголовком `X-Request-ID`.
        """
        request_id = request.headers.get('X-Request-ID') or str(uuid4())
        request.state.request_id = request_id
        started_at = perf_counter()
        response = await call_next(request)
        duration_ms = round((perf_counter() - started_at) * 1000, 3)
        response.headers['X-Request-ID'] = request_id
        logger.info(
            'http_request',
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    @app.middleware('http')
    async def graceful_shutdown_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Отклонить новый HTTP-запрос, если приложение завершает работу.

        Args:
            request: Входящий HTTP-запрос.
            call_next: Следующий обработчик в middleware-цепочке.

        Returns:
            Ответ приложения или `503`, если приложение завершает работу.
        """
        if controller.is_shutting_down:
            request_id = getattr(request.state, 'request_id', request.headers.get('X-Request-ID') or str(uuid4()))
            return JSONResponse(
                status_code=503,
                content={'detail': 'Service is shutting down'},
                headers={'Connection': 'close', 'X-Request-ID': request_id},
            )

        return await call_next(request)

    register_error_handlers(app)

    # Подключаем основной роутер (уже содержит все под-роутеры)
    app.include_router(app_router)

    return app


app = create_app()

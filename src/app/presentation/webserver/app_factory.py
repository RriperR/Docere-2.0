"""Точка входа FastAPI-приложения."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.infrastructure.config.paths import DEFAULT_ENV_FILE
from app.infrastructure.config.settings import get_settings
from app.infrastructure.db.session import close_db_connections
from app.presentation.router import router as app_router
from app.presentation.webserver.error_handlers import register_error_handlers
from app.presentation.webserver.error_schemas import ErrorResponseSchema
from app.presentation.webserver.graceful_shutdown import GracefulShutdownController


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
            return JSONResponse(
                status_code=503,
                content={'detail': 'Service is shutting down'},
                headers={'Connection': 'close'},
            )

        return await call_next(request)

    register_error_handlers(app)

    # Подключаем основной роутер (уже содержит все под-роутеры)
    app.include_router(app_router)

    return app


app = create_app()

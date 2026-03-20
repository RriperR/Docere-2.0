"""Точка входа FastAPI-приложения."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.infrastructure.config.paths import DEFAULT_ENV_FILE
from app.infrastructure.config.settings import get_settings
from app.presentation.router import router as app_router
from app.presentation.webserver.error_handlers import register_error_handlers
from app.presentation.webserver.error_schemas import ErrorResponseSchema


def create_app(*, env_file: Path | None = DEFAULT_ENV_FILE) -> FastAPI:
    """Создать и настроить экземпляр FastAPI.

    Args:
        env_file: Путь до dotenv-файла. `None` отключает чтение `.env`.

    Returns:
        Готовое приложение FastAPI.
    """

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Проверить настройки на старте приложения.

        Yields:
            Управление жизненным циклом FastAPI.
        """
        get_settings(env_file=env_file)
        yield

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
    register_error_handlers(app)

    # Подключаем основной роутер (уже содержит все под-роутеры)
    app.include_router(app_router)

    return app


app = create_app()

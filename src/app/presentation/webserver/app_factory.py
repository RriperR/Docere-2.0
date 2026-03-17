"""Точка входа FastAPI-приложения."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.infrastructure.config.settings import validate_settings
from app.presentation.router import router as app_router
from app.presentation.webserver.error_handlers import register_error_handlers
from app.presentation.webserver.error_schemas import ErrorResponseSchema


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Проверить настройки на старте приложения.

    Yields:
        Управление жизненным циклом FastAPI.
    """
    validate_settings()
    yield


def create_app() -> FastAPI:
    """Создать и настроить экземпляр FastAPI.

    Returns:
        Готовое приложение FastAPI.
    """
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

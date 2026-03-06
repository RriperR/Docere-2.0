"""Точка входа FastAPI-приложения."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.infrastructure.settings import validate_settings
from app.presentation.rest.auth.router import router as auth_router
from app.presentation.webserver.health.router import router as health_router


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
    app = FastAPI(title='Docere Service', lifespan=lifespan)
    app.include_router(health_router, prefix='/api')
    app.include_router(auth_router, prefix='/api')
    return app


app = create_app()

"""Основной роутер приложения — агрегирует все эндпоинты."""

from fastapi import APIRouter

from app.presentation.rest.router import router as rest_router
from app.presentation.webserver.router import router as webserver_router

# Создаём корневой роутер для всего приложения
router = APIRouter()

# Подключаем все под-роутеры
# Префиксы уже заданы внутри роутеров, поэтому не указываем здесь
router.include_router(rest_router)
router.include_router(webserver_router)

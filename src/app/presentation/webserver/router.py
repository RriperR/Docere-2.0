"""Webserver роутер — агрегирует служебные эндпоинты."""

from fastapi import APIRouter

from app.presentation.webserver.health.router import router as health_router

# Создаём роутер для служебных эндпоинтов
router = APIRouter(prefix='/api', tags=['Webserver'])

# Подключаем служебные роутеры
router.include_router(health_router)

"""REST API роутер — агрегирует все бизнес-эндпоинты."""

from fastapi import APIRouter

from app.presentation.rest.auth.router import router as auth_router
from app.presentation.rest.records.router import router as records_router

# Создаём роутер для всех REST эндпоинтов
router = APIRouter(prefix='/api', tags=['REST API'])

# Подключаем бизнес-роутеры
router.include_router(auth_router)
router.include_router(records_router)

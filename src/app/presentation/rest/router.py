"""REST API роутер — агрегирует все бизнес-эндпоинты."""

from fastapi import APIRouter

from app.presentation.rest.auth.router import router as auth_router

# Создаём роутер для всех REST эндпоинтов
router = APIRouter(prefix='/api', tags=['REST API'])

# Подключаем бизнес-роутеры
router.include_router(auth_router)

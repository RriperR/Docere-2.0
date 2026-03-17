"""Основной роутер приложения."""

from fastapi import APIRouter

from app.presentation.rest.router import router as rest_router

router = APIRouter()
router.include_router(rest_router)

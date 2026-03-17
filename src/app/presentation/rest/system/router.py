"""Агрегатор системных REST-endpoint-ов."""

from fastapi import APIRouter

from app.presentation.rest.system.health.router import router as health_router

router = APIRouter(prefix='/api', tags=['system'])
router.include_router(health_router)

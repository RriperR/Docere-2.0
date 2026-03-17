"""Агрегатор REST-endpoint-ов."""

from fastapi import APIRouter

from app.presentation.rest.public.v1.router import router as public_v1_router
from app.presentation.rest.system.router import router as system_router

router = APIRouter()
router.include_router(public_v1_router)
router.include_router(system_router)

"""Агрегатор публичных REST-endpoint-ов версии v1."""

from fastapi import APIRouter

from app.presentation.rest.public.v1.auth.router import router as auth_router
from app.presentation.rest.public.v1.records.router import router as records_router

router = APIRouter(prefix='/api', tags=['public'])
router.include_router(auth_router)
router.include_router(records_router)

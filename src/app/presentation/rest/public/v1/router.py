"""Агрегатор публичных REST-endpoint-ов версии v1."""

from fastapi import APIRouter

from app.presentation.rest.public.v1.admin.router import router as admin_router
from app.presentation.rest.public.v1.archives.router import router as archives_router
from app.presentation.rest.public.v1.auth.router import router as auth_router
from app.presentation.rest.public.v1.doctor_role_applications.router import router as doctor_role_applications_router
from app.presentation.rest.public.v1.patients.router import router as patients_router
from app.presentation.rest.public.v1.records.router import router as records_router
from app.presentation.rest.public.v1.share_requests.router import router as share_requests_router

router = APIRouter(prefix='/api', tags=['public'])
router.include_router(admin_router)
router.include_router(archives_router)
router.include_router(auth_router)
router.include_router(doctor_role_applications_router)
router.include_router(patients_router)
router.include_router(records_router)
router.include_router(share_requests_router)

"""Dependency-фабрики для системного health-endpoint."""

from fastapi import Depends

from app.application.use_cases.health.get_health_status.use_case import GetHealthStatusUseCase
from app.infrastructure.config.settings import get_settings


def get_health_status_use_case() -> GetHealthStatusUseCase:
    """Создать use-case для health-check.

    Returns:
        Экземпляр `GetHealthStatusUseCase`.
    """
    settings = get_settings()
    return GetHealthStatusUseCase(service_name=settings.service_name)


health_status_use_case_dependency = Depends(get_health_status_use_case)

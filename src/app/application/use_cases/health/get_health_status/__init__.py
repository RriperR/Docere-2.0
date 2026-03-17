"""Сценарий получения состояния сервиса."""

from app.application.use_cases.health.get_health_status.dtos import HealthResponseDTO
from app.application.use_cases.health.get_health_status.use_case import GetHealthStatusUseCase

__all__ = ['GetHealthStatusUseCase', 'HealthResponseDTO']

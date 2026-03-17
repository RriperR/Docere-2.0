"""Системный health-endpoint."""

from app.presentation.rest.system.health.dependencies import health_status_use_case_dependency
from app.presentation.rest.system.health.router import router

__all__ = ['router', 'health_status_use_case_dependency']

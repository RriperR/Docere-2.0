"""DTO ответа health-check."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.domain.entities.health_status import HealthStatus


@dataclass(frozen=True, slots=True)
class HealthResponse:
    """Структура ответа health-endpoint."""

    service: str
    status: Literal['ok']
    timestamp_utc: datetime

    @classmethod
    def from_domain(cls, health_status: HealthStatus) -> 'HealthResponse':
        """Преобразовать доменную сущность в DTO.

        Args:
            health_status: Доменный объект состояния сервиса.

        Returns:
            Экземпляр DTO для API-ответа.
        """
        return cls(
            service=health_status.service,
            status=health_status.status,
            timestamp_utc=health_status.timestamp_utc,
        )

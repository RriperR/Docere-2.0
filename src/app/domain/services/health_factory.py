"""Доменные фабрики, связанные с health-состоянием сервиса."""

from app.domain.entities.health_status import HealthStatus
from app.domain.interfaces.clock import Clock


class HealthFactory:
    """Фабрика доменной сущности состояния сервиса."""

    def __init__(self, clock: Clock) -> None:
        """Инициализировать фабрику.

        Args:
            clock: Интерфейс часов.
        """
        self._clock = clock

    def healthy(self, service_name: str) -> HealthStatus:
        """Построить состояние исправного сервиса.

        Args:
            service_name: Имя сервиса.

        Returns:
            Доменная сущность состояния сервиса.
        """
        return HealthStatus(service=service_name, status='ok', timestamp_utc=self._clock.now_utc())

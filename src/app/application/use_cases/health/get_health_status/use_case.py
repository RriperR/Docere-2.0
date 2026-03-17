"""Сценарий формирования состояния сервиса для health-check."""

from datetime import datetime, UTC

from app.application.use_cases.health.get_health_status.dtos import HealthResponseDTO


class GetHealthStatusUseCase:
    """Сформировать DTO состояния сервиса."""

    def __init__(self, service_name: str) -> None:
        """Инициализировать use-case.

        Args:
            service_name: Имя сервиса.
        """
        self._service_name = service_name

    def execute(self) -> HealthResponseDTO:
        """Построить ответ health-check.

        Returns:
            DTO ответа health-check.
        """
        return HealthResponseDTO(
            service=self._service_name,
            status='ok',
            timestamp_utc=datetime.now(tz=UTC),
        )

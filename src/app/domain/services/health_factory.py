from app.domain.entities.health_status import HealthStatus
from app.domain.interfaces.clock import Clock


class HealthFactory:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock

    def healthy(self, service_name: str) -> HealthStatus:
        return HealthStatus(service=service_name, status='ok', timestamp_utc=self._clock.now_utc())

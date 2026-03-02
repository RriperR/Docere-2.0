from app.application.dto.health_response import HealthResponse
from app.application.ports.clock import ClockPort
from app.domain.services.health_factory import HealthFactory


class GetHealthStatus:
    def __init__(self, clock: ClockPort, service_name: str) -> None:
        self._clock = clock
        self._service_name = service_name

    def execute(self) -> HealthResponse:
        health_factory = HealthFactory(clock=self._clock)
        domain_entity = health_factory.healthy(service_name=self._service_name)
        return HealthResponse.from_domain(domain_entity)

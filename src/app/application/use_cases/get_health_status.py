from app.application.dto.health_response import HealthResponse
from app.domain.services.health_factory import HealthFactory


class GetHealthStatus:
    def __init__(self, health_factory: HealthFactory, service_name: str) -> None:
        self._health_factory = health_factory
        self._service_name = service_name

    def execute(self) -> HealthResponse:
        domain_entity = self._health_factory.healthy(service_name=self._service_name)
        return HealthResponse.from_domain(domain_entity)

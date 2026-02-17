from fastapi import APIRouter

from app.application.use_cases.get_health_status import GetHealthStatus
from app.domain.services.health_factory import HealthFactory
from app.infrastructure.settings import AppSettings
from app.infrastructure.time.system_clock import SystemClock
from app.presentation.schemas.health import HealthSchema

router = APIRouter(tags=['health'])
settings = AppSettings()


@router.get('/health', response_model=HealthSchema)
def get_health() -> HealthSchema:
    use_case = GetHealthStatus(
        health_factory=HealthFactory(clock=SystemClock()),
        service_name=settings.service_name,
    )
    response = use_case.execute()
    return HealthSchema(service=response.service, status=response.status, timestamp_utc=response.timestamp_utc)

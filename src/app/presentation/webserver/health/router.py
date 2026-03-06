"""HTTP-роут health-check."""

from fastapi import APIRouter

from app.application.use_cases.get_health_status import GetHealthStatus
from app.infrastructure.settings import get_settings
from app.infrastructure.time.system_clock import SystemClock
from app.presentation.webserver.health.schemas import HealthSchema

router = APIRouter(tags=['health'])


@router.get('/health', response_model=HealthSchema)
def get_health() -> HealthSchema:
    """Вернуть состояние доступности сервиса.

    Returns:
        Ответ `health` с именем сервиса и UTC-временем.
    """
    settings = get_settings()
    use_case = GetHealthStatus(
        clock=SystemClock(),
        service_name=settings.service_name,
    )
    response = use_case.execute()
    return HealthSchema(service=response.service, status=response.status, timestamp_utc=response.timestamp_utc)

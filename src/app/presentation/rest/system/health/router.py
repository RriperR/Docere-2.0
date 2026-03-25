"""HTTP-роуты health-check."""

from fastapi import APIRouter

from app.application.use_cases.health.get_health_status.use_case import GetHealthStatusUseCase
from app.presentation.rest.system.health.dependencies import health_status_use_case_dependency
from app.presentation.rest.system.health.schemas import HealthSchema

router = APIRouter(tags=['health'])


@router.get('/health', response_model=HealthSchema)
def get_health(
    use_case: GetHealthStatusUseCase = health_status_use_case_dependency,
) -> HealthSchema:
    """Вернуть состояние доступности сервиса.

    Args:
        use_case: Use-case формирования health-ответа.

    Returns:
        Ответ `health` с именем сервиса и UTC-временем.
    """
    response = use_case.execute()
    return HealthSchema(service=response.service, status=response.status, timestamp_utc=response.timestamp_utc)

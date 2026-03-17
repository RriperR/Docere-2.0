"""DTO сценария health-check."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class HealthResponseDTO:
    """Структура ответа health-endpoint."""

    service: str
    status: Literal['ok']
    timestamp_utc: datetime

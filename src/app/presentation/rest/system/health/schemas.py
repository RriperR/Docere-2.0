"""Pydantic-схемы для health-эндпоинта."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthSchema(BaseModel):
    """Схема ответа health-check."""

    service: str
    status: Literal['ok']
    timestamp_utc: datetime

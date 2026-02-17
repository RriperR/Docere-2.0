from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class HealthStatus:
    service: str
    status: Literal['ok']
    timestamp_utc: datetime

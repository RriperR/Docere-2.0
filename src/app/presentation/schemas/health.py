from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthSchema(BaseModel):
    service: str
    status: Literal['ok']
    timestamp_utc: datetime

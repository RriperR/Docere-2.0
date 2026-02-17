from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now_utc(self) -> datetime: ...

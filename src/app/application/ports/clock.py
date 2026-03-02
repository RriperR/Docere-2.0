from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    def now_utc(self) -> datetime: ...

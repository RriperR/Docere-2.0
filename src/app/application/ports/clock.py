"""Контракт часов для application-слоя."""

from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    """Порт получения текущего UTC-времени."""

    def now_utc(self) -> datetime:
        """Вернуть текущее время в UTC.

        Returns:
            Текущее UTC-время.
        """
        ...

"""Доменный интерфейс часов."""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Контракт получения текущего времени."""

    def now_utc(self) -> datetime:
        """Вернуть текущее UTC-время.

        Returns:
            Текущее UTC-время.
        """
        ...

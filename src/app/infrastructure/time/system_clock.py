"""Системная реализация часов."""

from datetime import datetime, UTC


class SystemClock:
    """Реализация часов на базе системного времени."""

    def now_utc(self) -> datetime:
        """Вернуть текущее системное время в UTC.

        Returns:
            Текущее UTC-время.
        """
        return datetime.now(tz=UTC)

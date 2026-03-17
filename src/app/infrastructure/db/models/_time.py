"""Вспомогательные функции времени для ORM-моделей."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo('Europe/Moscow')


def moscow_now() -> datetime:
    """Вернуть текущее время в часовом поясе Москвы.

    Returns:
        Текущее время в часовом поясе `Europe/Moscow`.
    """
    return datetime.now(tz=MOSCOW_TZ)

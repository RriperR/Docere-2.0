"""Общие хелперы сериализации REST-схем."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import PlainSerializer

DISPLAY_TZ = ZoneInfo('Europe/Moscow')


def _to_display_tz(value: datetime) -> datetime:
    """Перевести момент времени в зону отображения.

    Штампы времени хранятся в UTC. Значения без зоны трактуются как UTC.

    Args:
        value: Момент времени из доменной модели.

    Returns:
        Тот же момент времени в зоне ``DISPLAY_TZ``.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(DISPLAY_TZ)


# Тип datetime, который в ответах API отдаётся в зоне отображения (Europe/Moscow).
MoscowDatetime = Annotated[datetime, PlainSerializer(_to_display_tz, return_type=datetime)]

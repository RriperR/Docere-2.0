"""Вспомогательные функции времени для ORM-моделей."""

from __future__ import annotations

from datetime import datetime, UTC


def utc_now() -> datetime:
    """Вернуть текущий момент времени в UTC.

    Штампы времени хранятся в UTC; перевод в зону отображения (например,
    Europe/Moscow) выполняется на presentation-границе.

    Returns:
        Текущий момент времени с зоной UTC.
    """
    return datetime.now(UTC)

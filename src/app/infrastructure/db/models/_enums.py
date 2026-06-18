"""Вспомогательные функции для объявления enum-колонок ORM-моделей."""

from __future__ import annotations

from enum import StrEnum


def enum_values(enum_class: type[StrEnum]) -> list[str]:
    """Вернуть значения перечисления для SQLAlchemy ``values_callable``.

    Args:
        enum_class: Класс строкового перечисления.

    Returns:
        Список строковых значений перечисления в порядке объявления.
    """
    return [item.value for item in enum_class]

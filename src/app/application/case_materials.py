"""Фильтры поиска в выбранных материалах клинического случая."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class MaterialFilters:
    """Серверные фильтры без OCR и чтения содержимого PDF."""

    query: str = ''
    record_type: str | None = None
    status: str | None = None
    date_from: date | None = None
    date_to: date | None = None

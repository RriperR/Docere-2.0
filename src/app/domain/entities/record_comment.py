"""Доменные сущности комментариев к записям."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RecordComment:
    """Append-only комментарий к медицинской записи."""

    id: UUID
    record_id: UUID
    author_user_id: UUID
    body: str
    created_at: datetime

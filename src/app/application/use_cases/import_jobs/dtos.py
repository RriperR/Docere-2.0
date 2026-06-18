"""DTO use cases ImportJob."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ImportJobDTO:
    """Проекция задания импорта архива."""

    id: UUID
    uploaded_by_user_id: UUID
    status: str
    original_filename: str | None
    archive_storage_key: str | None
    size_bytes: int | None
    report_json: dict[str, object]
    created_at: datetime
    finished_at: datetime | None

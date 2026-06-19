"""Доменная сущность задания импорта архива."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ImportJobStatus(StrEnum):
    """Статусы задания импорта архива."""

    QUEUED = 'queued'
    RUNNING = 'running'
    NEEDS_REVIEW = 'needs_review'
    COMPLETED = 'completed'
    FAILED = 'failed'
    COMPLETED_WITH_WARNINGS = 'completed_with_warnings'


@dataclass(frozen=True, slots=True)
class ImportJob:
    """Задание импорта загруженного архива."""

    id: UUID
    uploaded_by_user_id: UUID
    status: ImportJobStatus
    original_filename: str | None
    archive_storage_key: str | None
    size_bytes: int | None
    report_json: dict[str, object]
    created_at: datetime
    finished_at: datetime | None

"""Pydantic-схемы REST-эндпоинтов архивов."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.presentation.rest.serialization import MoscowDatetime


class ImportJobResponseSchema(BaseModel):
    """Схема ответа ImportJob."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    uploaded_by_user_id: UUID
    status: str
    original_filename: str | None
    archive_storage_key: str | None
    size_bytes: int | None
    report_json: dict[str, object]
    created_at: MoscowDatetime
    finished_at: MoscowDatetime | None

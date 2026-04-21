"""Pydantic-схемы API sharing медицинских записей."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CreateShareRequestSchema(BaseModel):
    """Тело запроса на sharing выбранных медицинских записей."""

    to_user_email: EmailStr
    record_ids: list[UUID] = Field(min_length=1)
    message: str | None = Field(default=None, max_length=2000)


class ShareUserResponseSchema(BaseModel):
    """Краткая публичная проекция пользователя в sharing API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fio: str
    email: str
    role: str


class RecordShareResponseSchema(BaseModel):
    """Проекция отдельной записи внутри sharing request."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    record_id: UUID
    patient_passport_id: UUID | None
    status: str
    created_at: datetime
    responded_at: datetime | None
    revoked_at: datetime | None


class ShareRequestResponseSchema(BaseModel):
    """Проекция request-level sharing-запроса."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    from_user: ShareUserResponseSchema
    to_user: ShareUserResponseSchema
    status: str
    message: str | None
    shares: tuple[RecordShareResponseSchema, ...]
    created_at: datetime
    responded_at: datetime | None
    cancelled_at: datetime | None
    revoked_at: datetime | None


class CreateShareRequestResponseSchema(BaseModel):
    """Ответ на создание sharing-запроса с информацией о пропущенных дублях."""

    request: ShareRequestResponseSchema | None
    skipped_record_ids: tuple[UUID, ...]

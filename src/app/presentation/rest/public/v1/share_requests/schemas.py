"""Pydantic-схемы API sharing медицинских записей."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.presentation.rest.serialization import MoscowDatetime


class CreateShareRequestSchema(BaseModel):
    """Тело запроса на sharing выбранных медицинских записей."""

    to_user_email: EmailStr
    record_ids: list[UUID] = Field(min_length=1)
    message: str | None = Field(default=None, max_length=2000)
    expires_at: date | None = None

    @field_validator('expires_at')
    @classmethod
    def validate_expires_at(cls, value: date | None) -> date | None:
        """Запретить создание новых sharing-запросов с уже истёкшим сроком.

        Returns:
            Валидная дата истечения или ``None``.

        Raises:
            ValueError: Если дата уже в прошлом.
        """
        if value is not None and value < date.today():
            raise ValueError('expires_at must be today or in the future')
        return value


class ShareUserResponseSchema(BaseModel):
    """Краткая публичная проекция пользователя в sharing API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fio: str
    email: str
    role: str


class ShareRecipientResponseSchema(BaseModel):
    """Пользователь-кандидат для выбора получателя sharing."""

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
    title: str | None
    record_type: str
    event_date: date
    patient_fio: str | None
    patient_passport_id: UUID | None
    attachments_count: int
    comments_count: int
    status: str
    created_at: MoscowDatetime
    responded_at: MoscowDatetime | None
    revoked_at: MoscowDatetime | None


class ShareRequestResponseSchema(BaseModel):
    """Проекция request-level sharing-запроса."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    from_user: ShareUserResponseSchema
    to_user: ShareUserResponseSchema
    status: str
    message: str | None
    expires_at: MoscowDatetime | None
    shares: tuple[RecordShareResponseSchema, ...]
    created_at: MoscowDatetime
    responded_at: MoscowDatetime | None
    cancelled_at: MoscowDatetime | None
    revoked_at: MoscowDatetime | None


class CreateShareRequestResponseSchema(BaseModel):
    """Ответ на создание sharing-запроса с информацией о пропущенных дублях."""

    request: ShareRequestResponseSchema | None
    skipped_record_ids: tuple[UUID, ...]

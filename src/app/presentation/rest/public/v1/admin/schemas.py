"""Pydantic-схемы admin endpoints."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class CreateStaffUserRequestSchema(BaseModel):
    """Тело запроса создания врача или администратора."""

    fio: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str = Field(min_length=5, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    role: Literal['doctor', 'admin']

    @field_validator('fio', 'phone')
    @classmethod
    def normalize_non_empty_text(cls, value: str) -> str:
        """Провалидировать строку без пустого значения.

        Args:
            value: Исходное значение.

        Returns:
            Значение без крайних пробелов.

        Raises:
            ValueError: Если строка пустая.
        """
        normalized = value.strip()
        if not normalized:
            raise ValueError('value must not be empty')
        return normalized


class AuditEventResponseSchema(BaseModel):
    """Событие audit log для административного UI."""

    id: UUID
    actor_user_id: UUID | None
    actor_fio: str | None
    actor_email: EmailStr | None
    event_type: str
    entity_type: str
    entity_id: UUID
    metadata_json: dict[str, object]
    created_at: datetime


class AdminUserResponseSchema(BaseModel):
    """Пользователь в административном списке."""

    id: UUID
    fio: str
    email: EmailStr
    phone: str
    date_of_birth: date | None
    role: str
    status: str
    created_at: datetime
    updated_at: datetime

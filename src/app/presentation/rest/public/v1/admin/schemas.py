"""Pydantic-схемы admin endpoints."""

from __future__ import annotations

from typing import Literal

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

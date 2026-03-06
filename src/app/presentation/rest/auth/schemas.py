"""Pydantic-схемы для auth-эндпоинтов."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterPatientRequestSchema(BaseModel):
    """Тело запроса регистрации пациента."""

    fio: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str = Field(min_length=5, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    date_of_birth: date | None = None

    @field_validator('fio')
    @classmethod
    def validate_fio(cls, value: str) -> str:
        """Провалидировать и нормализовать ФИО.

        Args:
            value: Исходное значение ФИО.

        Returns:
            Нормализованное ФИО без лишних пробелов.

        Raises:
            ValueError: Если ФИО пустое после нормализации.
        """
        normalized = value.strip()
        if not normalized:
            raise ValueError('fio must not be empty')
        return normalized

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, value: str) -> str:
        """Провалидировать и нормализовать номер телефона.

        Args:
            value: Исходное значение телефона.

        Returns:
            Нормализованный телефон без лишних пробелов.

        Raises:
            ValueError: Если телефон пустой после нормализации.
        """
        normalized = value.strip()
        if not normalized:
            raise ValueError('phone must not be empty')
        return normalized


class LoginRequestSchema(BaseModel):
    """Тело запроса входа пользователя."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshTokenRequestSchema(BaseModel):
    """Тело запроса обновления токенов."""

    refresh_token: str = Field(min_length=1, max_length=4096)


class AuthTokenResponseSchema(BaseModel):
    """Схема ответа с парой access/refresh токенов."""

    access_token: str
    refresh_token: str
    token_type: str


class AuthUserResponseSchema(BaseModel):
    """Схема ответа с профилем аутентифицированного пользователя."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fio: str
    email: EmailStr
    phone: str
    date_of_birth: date | None
    role: str
    status: str

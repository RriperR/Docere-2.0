from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterPatientRequestSchema(BaseModel):
    fio: str = Field(min_length=1, max_length=255)
    email: EmailStr
    phone: str = Field(min_length=5, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    date_of_birth: date | None = None

    @field_validator('fio')
    @classmethod
    def validate_fio(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('fio must not be empty')
        return normalized

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError('phone must not be empty')
        return normalized


class LoginRequestSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthTokenResponseSchema(BaseModel):
    access_token: str
    token_type: str


class AuthUserResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fio: str
    email: EmailStr
    phone: str
    date_of_birth: date | None
    role: str
    status: str

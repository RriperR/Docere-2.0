"""Pydantic-схемы ошибок для OpenAPI и глобальных handlers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ErrorResponseSchema(BaseModel):
    """Унифицированная схема ответа об ошибке."""

    detail: Any
    status_code: int

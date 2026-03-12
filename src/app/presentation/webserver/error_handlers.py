"""Глобальные обработчики ошибок HTTP-приложения."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _build_error_response(
    status_code: int,
    detail: Any,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Построить унифицированный JSON-ответ об ошибке.

    Args:
        status_code: HTTP-статус ответа.
        detail: Детали ошибки.
        headers: Дополнительные HTTP-заголовки ответа.

    Returns:
        JSON-ответ с унифицированной структурой ошибки.
    """
    return JSONResponse(
        status_code=status_code,
        content={
            'detail': detail,
            'status_code': status_code,
        },
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Зарегистрировать глобальные обработчики ошибок приложения.

    Args:
        app: Экземпляр FastAPI-приложения.
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        """Вернуть унифицированный ответ для ожидаемых HTTP-ошибок.

        Args:
            _: Входящий HTTP-запрос.
            exc: Исключение FastAPI HTTPException.

        Returns:
            JSON-ответ с HTTP-ошибкой.
        """
        return _build_error_response(
            status_code=exc.status_code,
            detail=exc.detail,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(
        _: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Вернуть унифицированный ответ при ошибке валидации запроса.

        Args:
            _: Входящий HTTP-запрос.
            exc: Исключение ошибки валидации запроса.

        Returns:
            JSON-ответ с деталями валидации.
        """
        return _build_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        """Вернуть унифицированный ответ для необработанного исключения.

        Args:
            _: Входящий HTTP-запрос.
            exc: Необработанное исключение приложения.

        Returns:
            JSON-ответ с кодом 500.
        """
        logger.exception('Unhandled application exception', exc_info=exc)
        return _build_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Internal server error',
        )

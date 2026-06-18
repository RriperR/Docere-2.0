"""Фабрики HTTP-ошибок для presentation-слоя."""

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException, status


def raise_email_already_exists() -> NoReturn:
    """Выбросить HTTP 409 при конфликте email.

    Raises:
        HTTPException: Если пользователь с таким email уже существует.
    """
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail='User with this email already exists',
    )


def raise_invalid_credentials() -> NoReturn:
    """Выбросить HTTP 401 при неверных учетных данных.

    Raises:
        HTTPException: Если email/пароль некорректны.
    """
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Invalid email or password',
        headers={'WWW-Authenticate': 'Bearer'},
    )


def raise_unauthorized(detail: str) -> NoReturn:
    """Выбросить HTTP 401 с заданным описанием.

    Args:
        detail: Текст ошибки авторизации.

    Raises:
        HTTPException: Если запрос неавторизован.
    """
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={'WWW-Authenticate': 'Bearer'},
    )


def raise_forbidden(detail: str) -> NoReturn:
    """Выбросить HTTP 403 с заданным описанием.

    Args:
        detail: Текст ошибки авторизации.

    Raises:
        HTTPException: Если доступ к ресурсу запрещен.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )


def raise_not_found(detail: str) -> NoReturn:
    """Выбросить HTTP 404 с заданным описанием.

    Args:
        detail: Текст ошибки отсутствующего ресурса.

    Raises:
        HTTPException: Если ресурс не найден.
    """
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
    )


def raise_payload_too_large(detail: str) -> NoReturn:
    """Выбросить HTTP 413 с заданным описанием.

    Args:
        detail: Текст ошибки превышения размера.

    Raises:
        HTTPException: Если тело запроса превышает лимит.
    """
    raise HTTPException(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        detail=detail,
    )

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException, status


def raise_email_already_exists() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail='User with this email already exists',
    )


def raise_invalid_credentials() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Invalid email or password',
        headers={'WWW-Authenticate': 'Bearer'},
    )


def raise_unauthorized(detail: str) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={'WWW-Authenticate': 'Bearer'},
    )

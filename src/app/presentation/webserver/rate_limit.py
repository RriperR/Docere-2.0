"""Простой in-memory rate limiter для HTTP endpoints."""

from __future__ import annotations

from collections import defaultdict, deque
from time import monotonic

from fastapi import HTTPException, status

_WINDOW_SECONDS = 60
_MAX_ATTEMPTS = 5
_attempts: dict[str, deque[float]] = defaultdict(deque)


def check_auth_rate_limit(key: str) -> None:
    """Проверить лимит частоты auth-действий.

    Args:
        key: Ключ лимита, обычно `endpoint:email`.

    Raises:
        HTTPException: Если лимит превышен.
    """
    now = monotonic()
    bucket = _attempts[key]
    while bucket and now - bucket[0] > _WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail='Too many authentication attempts',
        )
    bucket.append(now)


def clear_auth_rate_limits() -> None:
    """Очистить накопленные лимиты для тестов."""
    _attempts.clear()

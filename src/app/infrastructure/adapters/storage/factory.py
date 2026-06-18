"""Фабрика файлового хранилища."""

from __future__ import annotations

from functools import lru_cache

from app.application.ports.storage.file_storage import FileStoragePort
from app.infrastructure.adapters.storage.s3_file_storage import S3FileStorageAdapter
from app.infrastructure.config.settings import get_settings


@lru_cache(maxsize=1)
def get_file_storage() -> FileStoragePort:
    """Создать и закешировать адаптер файлового хранилища.

    Returns:
        Адаптер файлового хранилища.
    """
    return S3FileStorageAdapter(settings=get_settings().storage)

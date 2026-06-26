"""Фабрики адаптеров импорта архивов."""

from __future__ import annotations

from app.infrastructure.adapters.import_jobs.zip_archive_reader import ZipArchiveReader
from app.infrastructure.config.settings import AppSettings, get_settings


def build_zip_archive_reader(settings: AppSettings | None = None) -> ZipArchiveReader:
    """Создать ZIP reader из настроек приложения.

    Args:
        settings: Настройки приложения. Если не переданы, читаются из окружения.

    Returns:
        Настроенный ZIP reader.
    """
    config = (settings or get_settings()).import_archive
    return ZipArchiveReader(
        max_files=config.max_files,
        max_file_size_bytes=config.max_file_size_bytes,
        max_total_uncompressed_size_bytes=config.max_total_uncompressed_size_bytes,
        max_compression_ratio=config.max_compression_ratio,
    )

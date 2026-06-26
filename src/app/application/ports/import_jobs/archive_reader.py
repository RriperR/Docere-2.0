"""Порт чтения импортируемого архива."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ArchiveFileDTO:
    """Файл, безопасно прочитанный из архива."""

    path: str
    filename: str
    size_bytes: int
    mime_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class ArchiveReadResult:
    """Результат чтения архива."""

    files: tuple[ArchiveFileDTO, ...]
    warnings: tuple[str, ...]


class ArchiveReaderPort(Protocol):
    """Абстракция чтения архива без привязки application к ZIP."""

    def read_files(self, *, archive_content: bytes) -> ArchiveReadResult:
        """Вернуть безопасные файлы архива."""

    def read_file(self, *, archive_content: bytes, path: str) -> ArchiveFileDTO | None:
        """Вернуть один безопасный файл архива по нормализованному пути."""

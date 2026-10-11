"""Порт безопасной упаковки отдельных документов."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class UploadedDocument:
    """Загруженный документ до сохранения в хранилище."""

    filename: str
    content: bytes


class DocumentBundlePort(Protocol):
    """Упаковка документов без зависимости application от ZIP."""

    def pack(self, documents: tuple[UploadedDocument, ...]) -> bytes:
        """Проверить форматы и вернуть безопасный ZIP.

        Args:
            documents: Исходные документы.

        Returns:
            Содержимое внутреннего архива.
        """
        ...

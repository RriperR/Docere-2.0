"""Порт чтения DICOM-метаданных."""

from __future__ import annotations

from typing import Protocol

from app.application.use_cases.import_jobs.dtos import DicomMetadata


class DicomMetadataReaderPort(Protocol):
    """Абстракция извлечения DICOM-метаданных."""

    def read_metadata(self, *, content: bytes, path: str) -> DicomMetadata | None:
        """Вернуть метаданные DICOM или None, если файл не похож на DICOM."""

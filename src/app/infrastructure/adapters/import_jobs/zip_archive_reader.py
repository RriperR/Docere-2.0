"""ZIP-адаптер чтения импортируемых архивов."""

from __future__ import annotations

import mimetypes
import re
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, LargeZipFile, ZipFile

from app.application.ports.import_jobs.archive_reader import ArchiveFileDTO, ArchiveReaderPort, ArchiveReadResult
from app.application.use_cases.import_jobs.errors import ArchiveExtractionError

MAX_ZIP_FILES = 1000
MAX_ZIP_FILE_SIZE_BYTES = 100 * 1024 * 1024
MAX_ZIP_TOTAL_UNCOMPRESSED_SIZE_BYTES = 500 * 1024 * 1024
MAX_ZIP_COMPRESSION_RATIO = 100
_TRASH_FILENAMES = {'', '.ds_store', 'thumbs.db', 'desktop.ini'}
_TRASH_PARTS = {'__macosx', '.trash'}


class ZipArchiveReader(ArchiveReaderPort):
    """Безопасно читает файлы ZIP-архива."""

    def __init__(
        self,
        *,
        max_files: int = MAX_ZIP_FILES,
        max_file_size_bytes: int = MAX_ZIP_FILE_SIZE_BYTES,
        max_total_uncompressed_size_bytes: int = MAX_ZIP_TOTAL_UNCOMPRESSED_SIZE_BYTES,
        max_compression_ratio: int = MAX_ZIP_COMPRESSION_RATIO,
    ) -> None:
        """Инициализировать лимиты чтения ZIP."""
        self._max_files = max_files
        self._max_file_size_bytes = max_file_size_bytes
        self._max_total_uncompressed_size_bytes = max_total_uncompressed_size_bytes
        self._max_compression_ratio = max_compression_ratio

    def read_files(self, *, archive_content: bytes) -> ArchiveReadResult:
        """Вернуть безопасные файлы архива.

        Returns:
            Прочитанные файлы и предупреждения о пропущенных элементах.

        Raises:
            ArchiveExtractionError: Если ZIP битый или невалидный.
        """
        warnings: list[str] = []
        files: list[ArchiveFileDTO] = []
        processed_files = 0
        total_uncompressed_size = 0

        try:
            archive = ZipFile(BytesIO(archive_content))
        except (BadZipFile, LargeZipFile) as error:
            raise ArchiveExtractionError('Archive is not a valid ZIP file') from error

        with archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                path = _safe_zip_path(info.filename)
                if path is None:
                    warnings.append(f'Skipped unsafe or system file: {info.filename}')
                    continue
                if processed_files >= self._max_files:
                    warnings.append(f'Skipped file over ZIP file count limit: {path}')
                    continue
                if info.file_size <= 0:
                    warnings.append(f'Skipped empty file: {path}')
                    continue
                if info.file_size > self._max_file_size_bytes:
                    warnings.append(f'Skipped file over size limit: {path}')
                    continue
                if total_uncompressed_size + info.file_size > self._max_total_uncompressed_size_bytes:
                    warnings.append(f'Skipped file over ZIP total uncompressed size limit: {path}')
                    continue
                if _compression_ratio(info.compress_size, info.file_size) > self._max_compression_ratio:
                    warnings.append(f'Skipped suspiciously compressed file: {path}')
                    continue

                try:
                    content = archive.read(info)
                except (BadZipFile, LargeZipFile) as error:
                    raise ArchiveExtractionError('Archive contains unreadable ZIP entries') from error
                files.append(
                    ArchiveFileDTO(
                        path=path,
                        filename=PurePosixPath(path).name,
                        size_bytes=info.file_size,
                        mime_type=mimetypes.guess_type(path)[0] or 'application/octet-stream',
                        content=content,
                    ),
                )
                processed_files += 1
                total_uncompressed_size += info.file_size

        return ArchiveReadResult(files=tuple(files), warnings=tuple(warnings))

    def read_file(self, *, archive_content: bytes, path: str) -> ArchiveFileDTO | None:
        """Вернуть один безопасный файл архива по нормализованному пути.

        Returns:
            Файл архива или None, если путь не найден/небезопасен.

        Raises:
            ArchiveExtractionError: Если ZIP битый или невалидный.
        """
        try:
            archive = ZipFile(BytesIO(archive_content))
        except (BadZipFile, LargeZipFile) as error:
            raise ArchiveExtractionError('Archive is not a valid ZIP file') from error

        with archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                safe_path = _safe_zip_path(info.filename)
                if safe_path != path:
                    continue
                if info.file_size <= 0 or info.file_size > self._max_file_size_bytes:
                    return None
                if _compression_ratio(info.compress_size, info.file_size) > self._max_compression_ratio:
                    return None
                try:
                    content = archive.read(info)
                except (BadZipFile, LargeZipFile) as error:
                    raise ArchiveExtractionError('Archive contains unreadable ZIP entries') from error
                return ArchiveFileDTO(
                    path=safe_path,
                    filename=PurePosixPath(safe_path).name,
                    size_bytes=info.file_size,
                    mime_type=mimetypes.guess_type(safe_path)[0] or 'application/octet-stream',
                    content=content,
                )
        return None


def _safe_zip_path(raw_path: str) -> str | None:
    raw_path = raw_path.replace('\\', '/')
    if raw_path.startswith('/'):
        return None
    if re.match(r'^[A-Za-z]:[/\\]', raw_path):
        return None

    raw_parts = raw_path.split('/')
    if any(part in {'..', '.'} for part in raw_parts):
        return None
    if any(part.casefold() in _TRASH_PARTS for part in raw_parts):
        return None
    raw_name = raw_parts[-1].casefold() if raw_parts else ''
    if raw_name in _TRASH_FILENAMES:
        return None
    if raw_parts and raw_parts[-1].startswith('._'):
        return None

    normalized = '/'.join(part for part in raw_parts if part)
    if not normalized:
        return None
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in {'..', '.'} for part in path.parts):
        return None
    return path.as_posix()


def _compression_ratio(compressed_size: int, uncompressed_size: int) -> float:
    if compressed_size <= 0:
        return float('inf')
    return uncompressed_size / compressed_size

"""Загрузка отдельных документов и авторизованное чтение исходников."""

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from app.application.ports.import_jobs.archive_reader import ArchiveReaderPort
from app.application.ports.import_jobs.document_bundle import DocumentBundlePort, UploadedDocument
from app.application.ports.repositories.import_jobs.port import ImportJobRepositoryPort
from app.application.ports.storage.file_storage import FileStoragePort
from app.application.use_cases.import_jobs.dtos import ImportJobDTO
from app.application.use_cases.import_jobs.errors import ImportJobNotFoundError
from app.application.use_cases.import_jobs.use_cases import CreateImportJobUseCase


def import_file_id(path: str) -> str:
    """Вернуть стабильный идентификатор файла внутри неизменяемого архива.

    Args:
        path: Нормализованный путь безопасного ZIP-reader.

    Returns:
        SHA-256 пути, не являющийся разрешением доступа.
    """
    return sha256(path.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ImportSourceFile:
    """Исходник для авторизованного просмотра."""

    id: str
    filename: str
    mime_type: str
    content: bytes


class UploadDocumentsUseCase:
    """Провести отдельные документы через существующий импорт."""

    def __init__(self, bundle: DocumentBundlePort, create: CreateImportJobUseCase) -> None:
        """Связать безопасную упаковку и создание задания."""
        self._bundle = bundle
        self._create = create

    def execute(
        self, documents: tuple[UploadedDocument, ...], user_id: UUID, request_id: str | None, ai_requested: bool = False
    ) -> ImportJobDTO:
        """Упаковать файлы и создать единое задание проверки.

        Args:
            documents: Отдельные медицинские документы.
            user_id: Загрузивший пользователь.
            request_id: Идентификатор запроса.
            ai_requested: Явно выбранный автоматический AI-анализ.

        Returns:
            Задание, которое ничего не публикует в истории автоматически.
        """
        bundle = self._bundle.pack(documents)
        return self._create.execute(
            uploaded_by_user_id=user_id,
            original_filename='documents.zip',
            content=bundle.content,
            original_filenames=bundle.original_filenames,
            content_type='application/zip',
            request_id=request_id,
            ai_requested=ai_requested,
        )


class ReadImportSourceUseCase:
    """Читать только файлы из доступного отчёта импорта."""

    def __init__(self, jobs: ImportJobRepositoryPort, storage: FileStoragePort, reader: ArchiveReaderPort) -> None:
        """Связать проверку доступа с безопасным чтением архива."""
        self._jobs, self._storage, self._reader = jobs, storage, reader

    def execute(self, job_id: UUID, file_id: str, user_id: UUID, role: str) -> ImportSourceFile:
        """Вернуть исходник по идентификатору из отчёта.

        Args:
            job_id: Задание импорта.
            file_id: Идентификатор файла.
            user_id: Текущий пользователь.
            role: Его действующая роль.

        Returns:
            Проверенный исходный файл.

        Raises:
            ImportJobNotFoundError: Задание или исходник недоступен.
        """
        from app.application.use_cases.import_jobs.use_cases import _as_dict_list

        job = self._jobs.get_job(job_id=job_id, requested_by_user_id=user_id, requested_by_role=role)
        if job is None or not job.archive_storage_key:
            raise ImportJobNotFoundError
        file_infos = [
            f
            for p in _as_dict_list(job.report_json.get('patients'))
            for g in _as_dict_list(p.get('record_groups'))
            for f in _as_dict_list(g.get('files'))
        ]
        paths = [
            str(f.get('path', ''))
            for p in _as_dict_list(job.report_json.get('patients'))
            for g in _as_dict_list(p.get('record_groups'))
            for f in _as_dict_list(g.get('files'))
        ]
        path = next((p for p in paths if import_file_id(p) == file_id), None)
        if path is None:
            raise ImportJobNotFoundError
        source = self._reader.read_file(archive_content=self._storage.download(key=job.archive_storage_key), path=path)
        if source is None:
            raise ImportJobNotFoundError
        filename = next(
            (str(f.get('filename') or source.filename) for f in file_infos if str(f.get('path')) == path),
            source.filename,
        )
        return ImportSourceFile(file_id, filename, source.mime_type, source.content)

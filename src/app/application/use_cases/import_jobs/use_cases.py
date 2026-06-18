"""Сценарии создания и чтения ImportJob."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.application.ports.repositories.import_jobs.port import ImportJobRepositoryPort
from app.application.ports.storage.file_storage import FileStoragePort
from app.application.use_cases.import_jobs.dtos import ImportJobDTO
from app.application.use_cases.import_jobs.errors import ImportJobNotFoundError, ImportJobValidationError
from app.domain.entities.import_job import ImportJob


class CreateImportJobUseCase:
    """Сохранить ZIP-архив и создать ImportJob."""

    def __init__(self, repository: ImportJobRepositoryPort, storage: FileStoragePort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий ImportJob.
            storage: Файловое хранилище архивов.
        """
        self._repository = repository
        self._storage = storage

    def execute(
        self,
        *,
        uploaded_by_user_id: UUID,
        original_filename: str,
        content: bytes,
        content_type: str,
    ) -> ImportJobDTO:
        """Создать ImportJob из загруженного ZIP-архива.

        Args:
            uploaded_by_user_id: Пользователь, загрузивший архив.
            original_filename: Исходное имя файла.
            content: Бинарное содержимое архива.
            content_type: MIME-тип файла.

        Returns:
            Созданный ImportJob.

        Raises:
            ImportJobValidationError: Если файл не похож на ZIP-архив.
        """
        if not original_filename.lower().endswith('.zip') or not content.startswith(b'PK'):
            raise ImportJobValidationError

        storage_key = f'import-jobs/{uploaded_by_user_id}/{uuid4()}.zip'
        self._storage.upload(key=storage_key, content=content, content_type=content_type)
        job = self._repository.create_job(
            uploaded_by_user_id=uploaded_by_user_id,
            original_filename=original_filename,
            archive_storage_key=storage_key,
            size_bytes=len(content),
        )
        return _to_dto(job)


class GetImportJobUseCase:
    """Вернуть статус ImportJob."""

    def __init__(self, repository: ImportJobRepositoryPort) -> None:
        """Инициализировать use case.

        Args:
            repository: Репозиторий ImportJob.
        """
        self._repository = repository

    def execute(self, *, job_id: UUID, requested_by_user_id: UUID, requested_by_role: str) -> ImportJobDTO:
        """Вернуть ImportJob, если он доступен пользователю.

        Args:
            job_id: Идентификатор ImportJob.
            requested_by_user_id: Идентификатор текущего пользователя.
            requested_by_role: Роль текущего пользователя.

        Returns:
            ImportJob.

        Raises:
            ImportJobNotFoundError: Если задание не найдено или недоступно.
        """
        job = self._repository.get_job(
            job_id=job_id,
            requested_by_user_id=requested_by_user_id,
            requested_by_role=requested_by_role,
        )
        if job is None:
            raise ImportJobNotFoundError
        return _to_dto(job)


def _to_dto(job: ImportJob) -> ImportJobDTO:
    return ImportJobDTO(
        id=job.id,
        uploaded_by_user_id=job.uploaded_by_user_id,
        status=job.status.value,
        original_filename=job.original_filename,
        archive_storage_key=job.archive_storage_key,
        size_bytes=job.size_bytes,
        report_json=job.report_json,
        created_at=job.created_at,
        finished_at=job.finished_at,
    )

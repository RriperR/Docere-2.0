"""Фоновые Celery-задачи."""

from collections.abc import Callable
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.use_cases.import_jobs.dtos import ExtractImportDraftCommand
from app.application.use_cases.import_jobs.errors import ArchiveExtractionError
from app.application.use_cases.import_jobs.extractor import ExtractImportDraftUseCase
from app.infrastructure.adapters.import_jobs.patient_matcher import RepositoryPatientMatcher
from app.infrastructure.adapters.import_jobs.pydicom_metadata_reader import PydicomMetadataReader
from app.infrastructure.adapters.import_jobs.report_serializer import import_draft_result_to_json
from app.infrastructure.adapters.import_jobs.zip_archive_reader import ZipArchiveReader
from app.infrastructure.adapters.queue.celery_app import celery_app
from app.infrastructure.adapters.repositories.import_jobs.sqlalchemy_import_job_repository import (
    SqlAlchemyImportJobRepositoryAdapter,
)
from app.infrastructure.adapters.repositories.patient_cards.sqlalchemy_patient_card_repository import (
    SqlAlchemyPatientCardRepositoryAdapter,
)
from app.infrastructure.adapters.storage.factory import get_file_storage
from app.infrastructure.db.models.auth.user import UserRow
from app.infrastructure.db.session import get_session_factory

TaskCallable = Callable[[], str]
TaskDecorator = Callable[[TaskCallable], TaskCallable]
task_decorator = cast(TaskDecorator, celery_app.task(name='docere.ping'))
ImportTaskCallable = Callable[[str], None]
import_task_decorator = cast(
    Callable[[ImportTaskCallable], ImportTaskCallable],
    celery_app.task(name='docere.import_job', soft_time_limit=900, time_limit=960),
)


@task_decorator
def ping() -> str:
    """Проверить доступность воркера.

    Returns:
        Строка `pong`.
    """
    return 'pong'


@import_task_decorator
def process_import_job(job_id: str) -> None:
    """Обработать загруженный архив ImportJob.

    Worker извлекает best-effort черновик из произвольного ZIP и сохраняет его
    для последующего review пользователем.

    Args:
        job_id: Идентификатор ImportJob.
    """
    with get_session_factory()() as session:
        repository = SqlAlchemyImportJobRepositoryAdapter(session=session)
        job = repository.mark_running(job_id=UUID(job_id))
        if job is None or job.archive_storage_key is None:
            return
        try:
            archive_content = get_file_storage().download(key=job.archive_storage_key)
            patient_repository = SqlAlchemyPatientCardRepositoryAdapter(session=session)
            use_case = ExtractImportDraftUseCase(
                archive_reader=ZipArchiveReader(),
                dicom_metadata_reader=PydicomMetadataReader(),
                patient_matcher=RepositoryPatientMatcher(patient_repository),
            )
            result = use_case.execute(
                ExtractImportDraftCommand(
                    archive_filename=job.original_filename or 'archive.zip',
                    archive_content=archive_content,
                    requested_by_user_id=job.uploaded_by_user_id,
                    requested_by_role=_user_role(session=session, user_id=job.uploaded_by_user_id),
                ),
            )
            repository.mark_needs_review(job_id=job.id, report_json=import_draft_result_to_json(result))
        except ArchiveExtractionError as exc:
            repository.mark_failed(
                job_id=job.id,
                report_json={
                    'message': 'Archive is not a valid ZIP file',
                    'errors': [str(exc)],
                    'source_archive': job.original_filename,
                },
            )
        except Exception as exc:
            repository.mark_failed(
                job_id=job.id,
                report_json={
                    'message': 'Archive processing failed',
                    'errors': [str(exc)],
                    'source_archive': job.original_filename,
                },
            )
        session.commit()


def _user_role(*, session: Session, user_id: UUID) -> str:
    role = session.scalar(select(UserRow.role).where(UserRow.id == user_id))
    if role is None:
        return 'doctor'
    return role.value

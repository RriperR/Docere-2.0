"""Фоновые Celery-задачи."""

from collections.abc import Callable
from time import monotonic
from typing import cast
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.use_cases.import_jobs.dtos import (
    ExtractImportDraftCommand,
    IMPORT_REPORT_SCHEMA_VERSION,
)
from app.application.use_cases.import_jobs.errors import ArchiveExtractionError
from app.application.use_cases.import_jobs.extractor import ExtractImportDraftUseCase
from app.domain.entities.import_job import ImportJobStatus
from app.infrastructure.adapters.import_jobs.factory import build_zip_archive_reader
from app.infrastructure.adapters.import_jobs.patient_matcher import RepositoryPatientMatcher
from app.infrastructure.adapters.import_jobs.pydicom_metadata_reader import PydicomMetadataReader
from app.infrastructure.adapters.import_jobs.report_serializer import import_draft_result_to_json
from app.infrastructure.adapters.queue.celery_app import celery_app
from app.infrastructure.adapters.queue.import_execution import claim_import, finish_import
from app.infrastructure.adapters.repositories.patient_cards.sqlalchemy_patient_card_repository import (
    SqlAlchemyPatientCardRepositoryAdapter,
)
from app.infrastructure.adapters.storage.factory import get_file_storage
from app.infrastructure.db.models.auth.user import UserRow
from app.infrastructure.db.session import get_session_factory

TaskCallable = Callable[[], str]
TaskDecorator = Callable[[TaskCallable], TaskCallable]
task_decorator = cast(TaskDecorator, celery_app.task(name='docere.ping'))
ImportTaskCallable = Callable[..., None]
import_task_decorator = cast(
    Callable[[ImportTaskCallable], ImportTaskCallable],
    celery_app.task(
        name='docere.import_job', soft_time_limit=900, time_limit=960, acks_late=True, reject_on_worker_lost=True
    ),
)
logger = structlog.get_logger(__name__)


@task_decorator
def ping() -> str:
    """Проверить доступность воркера.

    Returns:
        Строка `pong`.
    """
    return 'pong'


@import_task_decorator
def process_import_job(job_id: str, request_id: str | None = None) -> None:
    """Обработать загруженный архив ImportJob.

    Worker извлекает best-effort черновик из произвольного ZIP и сохраняет его
    для последующего review пользователем.

    Args:
        job_id: Идентификатор ImportJob.
        request_id: Идентификатор исходного HTTP-запроса.
    """
    token = uuid4()
    job = claim_import(UUID(job_id), token)
    if job is None:
        logger.info('import_duplicate_skipped', job_id=job_id, request_id=request_id)
        return
    if job.archive_storage_key is None:
        finish_import(job.id, token, ImportJobStatus.FAILED, {'message': 'Archive storage key is missing'})
        return
    with (
        structlog.contextvars.bound_contextvars(request_id=request_id, job_id=job_id),
        get_session_factory()() as session,
    ):
        started_at = monotonic()
        logger.info(
            'import_job_processing_started',
            job_id=str(job.id),
            size_bytes=job.size_bytes,
        )
        try:
            archive_content = get_file_storage().download(key=job.archive_storage_key)
            patient_repository = SqlAlchemyPatientCardRepositoryAdapter(session=session)
            use_case = ExtractImportDraftUseCase(
                archive_reader=build_zip_archive_reader(),
                dicom_metadata_reader=PydicomMetadataReader(),
                patient_matcher=RepositoryPatientMatcher(patient_repository),
            )
            original_names = job.report_json.get('original_filenames')
            result = use_case.execute(
                ExtractImportDraftCommand(
                    archive_filename=job.original_filename or 'archive.zip',
                    archive_content=archive_content,
                    requested_by_user_id=job.uploaded_by_user_id,
                    requested_by_role=_user_role(session=session, user_id=job.uploaded_by_user_id),
                    original_filenames={
                        str(path): name for path, name in original_names.items() if isinstance(name, str)
                    }
                    if isinstance(original_names, dict)
                    else None,
                ),
            )
            report = import_draft_result_to_json(result)
            final_status = ImportJobStatus.NEEDS_REVIEW
            logger.info(
                'import_attempt_processed',
                job_id=str(job.id),
                status='needs_review',
                files_total=result.files_total,
                warnings_count=len(result.warnings),
                duration_ms=round((monotonic() - started_at) * 1000, 3),
            )
        except ArchiveExtractionError as exc:
            final_status = ImportJobStatus.FAILED
            report = {
                'schema_version': IMPORT_REPORT_SCHEMA_VERSION,
                'message': 'Archive is not a valid ZIP file',
                'errors': [str(exc)],
                'source_archive': job.original_filename,
            }
            logger.info(
                'import_attempt_processed',
                job_id=str(job.id),
                status='failed',
                files_total=0,
                warnings_count=0,
                duration_ms=round((monotonic() - started_at) * 1000, 3),
                error=str(exc),
            )
        except Exception as exc:
            final_status = ImportJobStatus.FAILED
            report = {
                'schema_version': IMPORT_REPORT_SCHEMA_VERSION,
                'message': 'Archive processing failed',
                'errors': [str(exc)],
                'source_archive': job.original_filename,
            }
            logger.exception(
                'import_job_processing_failed',
                job_id=str(job.id),
                status='failed',
                duration_ms=round((monotonic() - started_at) * 1000, 3),
                error=str(exc),
            )
        # Чтение архива и поиск кандидатов не удерживают транзакцию записи задания.
        session.rollback()
    if finish_import(job.id, token, final_status, report):
        logger.info('import_job_processing_finished', job_id=job_id, request_id=request_id, status=final_status.value)
    else:
        logger.warning('import_stale_result_discarded', job_id=job_id, request_id=request_id)


def _user_role(*, session: Session, user_id: UUID) -> str:
    role = session.scalar(select(UserRow.role).where(UserRow.id == user_id))
    if role is None:
        return 'doctor'
    return role.value

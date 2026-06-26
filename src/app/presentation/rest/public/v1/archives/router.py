"""REST-роуты загрузки архивов пациентов."""

from __future__ import annotations

from contextlib import suppress
from typing import cast, Protocol
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, status, UploadFile
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.import_jobs.dtos import ImportJobDTO
from app.application.use_cases.import_jobs.errors import ImportJobNotFoundError, ImportJobValidationError
from app.application.use_cases.import_jobs.use_cases import (
    CreateImportJobUseCase,
    GetImportJobUseCase,
    ListImportJobsUseCase,
    ResolveImportJobUseCase,
)
from app.infrastructure.adapters.import_jobs.factory import build_zip_archive_reader
from app.infrastructure.adapters.queue.tasks import process_import_job
from app.infrastructure.adapters.repositories.audit_events import AuditEventRepositoryAdapter
from app.infrastructure.adapters.repositories.import_jobs.sqlalchemy_import_job_repository import (
    SqlAlchemyImportJobRepositoryAdapter,
)
from app.infrastructure.adapters.repositories.medical_records.sqlalchemy_medical_record_repository import (
    SqlAlchemyMedicalRecordRepositoryAdapter,
)
from app.infrastructure.adapters.repositories.patient_cards.sqlalchemy_patient_card_repository import (
    SqlAlchemyPatientCardRepositoryAdapter,
)
from app.infrastructure.adapters.storage.factory import get_file_storage
from app.presentation.rest.public.v1.archives.schemas import ImportJobResponseSchema, ResolveImportJobRequestSchema
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
)
from app.presentation.webserver.http_errors import raise_forbidden, raise_not_found, raise_payload_too_large

router = APIRouter(prefix='/archives', tags=['archives'])
archive_file_dependency = File(...)
MAX_ARCHIVE_SIZE_MB = 200
MAX_ARCHIVE_SIZE_BYTES = MAX_ARCHIVE_SIZE_MB * 1024 * 1024


class _CeleryTask(Protocol):
    def delay(self, *args: object, **kwargs: object) -> object:
        """Enqueue Celery task."""
        ...


def _build_repository(session: Session) -> SqlAlchemyImportJobRepositoryAdapter:
    return SqlAlchemyImportJobRepositoryAdapter(session=session)


def get_create_import_job_use_case(session: Session = db_session_dependency) -> CreateImportJobUseCase:
    """Создать use case загрузки архива.

    Returns:
        Настроенный use case.
    """
    return CreateImportJobUseCase(repository=_build_repository(session), storage=get_file_storage())


def get_import_job_use_case(session: Session = db_session_dependency) -> GetImportJobUseCase:
    """Создать use case чтения ImportJob.

    Returns:
        Настроенный use case.
    """
    return GetImportJobUseCase(repository=_build_repository(session))


def get_list_import_jobs_use_case(session: Session = db_session_dependency) -> ListImportJobsUseCase:
    """Создать use case списка ImportJob.

    Returns:
        Настроенный use case.
    """
    return ListImportJobsUseCase(repository=_build_repository(session))


def get_resolve_import_job_use_case(session: Session = db_session_dependency) -> ResolveImportJobUseCase:
    """Создать use case финализации ImportJob.

    Returns:
        Настроенный use case.
    """
    return ResolveImportJobUseCase(
        import_jobs=_build_repository(session),
        patient_cards=SqlAlchemyPatientCardRepositoryAdapter(session=session),
        medical_records=SqlAlchemyMedicalRecordRepositoryAdapter(session=session),
        storage=get_file_storage(),
        archive_reader=build_zip_archive_reader(),
    )


create_import_job_use_case_dependency = Depends(get_create_import_job_use_case)
get_import_job_use_case_dependency = Depends(get_import_job_use_case)
list_import_jobs_use_case_dependency = Depends(get_list_import_jobs_use_case)
resolve_import_job_use_case_dependency = Depends(get_resolve_import_job_use_case)


@router.post('/imports', response_model=ImportJobResponseSchema, status_code=status.HTTP_201_CREATED)
def create_import_job(
    file: UploadFile = archive_file_dependency,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: CreateImportJobUseCase = create_import_job_use_case_dependency,
    session: Session = db_session_dependency,
) -> ImportJobDTO:
    """Загрузить ZIP-архив и создать ImportJob.

    Returns:
        Созданный ImportJob.

    Raises:
        HTTPException: Если файл не является ZIP-архивом.
    """
    if file.size is not None and file.size > MAX_ARCHIVE_SIZE_BYTES:
        raise_payload_too_large(f'Archive exceeds maximum size {MAX_ARCHIVE_SIZE_MB} MB')
    content = file.file.read()
    if len(content) > MAX_ARCHIVE_SIZE_BYTES:
        raise_payload_too_large(f'Archive exceeds maximum size {MAX_ARCHIVE_SIZE_MB} MB')
    if current_user.role not in {'doctor', 'admin'}:
        raise_forbidden('Only doctors and admins can upload archives')
    try:
        job = use_case.execute(
            uploaded_by_user_id=current_user.id,
            original_filename=file.filename or 'archive.zip',
            content=content,
            content_type=file.content_type or 'application/zip',
        )
        AuditEventRepositoryAdapter(session).record(
            actor_user_id=current_user.id,
            event_type='import',
            entity_type='import_job',
            entity_id=job.id,
            metadata_json={'original_filename': job.original_filename, 'size_bytes': job.size_bytes},
        )
        session.commit()
        with suppress(Exception):
            cast(_CeleryTask, process_import_job).delay(str(job.id))
        return job
    except ImportJobValidationError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='ZIP archive is required') from exc
    except Exception:
        session.rollback()
        raise


@router.get('/imports', response_model=list[ImportJobResponseSchema])
def list_import_jobs(
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ListImportJobsUseCase = list_import_jobs_use_case_dependency,
) -> tuple[ImportJobDTO, ...]:
    """Вернуть последние задания импорта, доступные текущему пользователю.

    Returns:
        Список доступных заданий импорта.
    """
    if current_user.role not in {'doctor', 'admin'}:
        raise_forbidden('Only doctors and admins can view archive imports')
    return use_case.execute(
        requested_by_user_id=current_user.id,
        requested_by_role=current_user.role,
        limit=50,
    )


@router.get('/imports/{job_id}', response_model=ImportJobResponseSchema)
def get_import_job(
    job_id: UUID,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: GetImportJobUseCase = get_import_job_use_case_dependency,
) -> ImportJobDTO:
    """Вернуть статус ImportJob.

    Returns:
        Текущее состояние ImportJob.
    """
    try:
        return use_case.execute(
            job_id=job_id,
            requested_by_user_id=current_user.id,
            requested_by_role=current_user.role,
        )
    except ImportJobNotFoundError:
        raise_not_found('Import job not found')


@router.post('/imports/{job_id}/resolve', response_model=ImportJobResponseSchema)
def resolve_import_job(
    job_id: UUID,
    payload: ResolveImportJobRequestSchema,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: ResolveImportJobUseCase = resolve_import_job_use_case_dependency,
    session: Session = db_session_dependency,
) -> ImportJobDTO:
    """Финализировать ImportJob после пользовательского review.

    Returns:
        Обновленное состояние ImportJob.

    Raises:
        HTTPException: Если решение некорректно.
    """
    if current_user.role not in {'doctor', 'admin'}:
        raise_forbidden('Only doctors and admins can resolve imports')
    try:
        job = use_case.execute(
            job_id=job_id,
            actor_user_id=current_user.id,
            actor_role=current_user.role,
            actor_fio=current_user.fio,
            decisions=[decision.model_dump(mode='json') for decision in payload.decisions],
        )
        AuditEventRepositoryAdapter(session).record(
            actor_user_id=current_user.id,
            event_type='resolve_import',
            entity_type='import_job',
            entity_id=job.id,
            metadata_json={
                'patients_created': job.report_json.get('patients_created', 0),
                'records_created': job.report_json.get('records_created', 0),
                'attachments_created': job.report_json.get('attachments_created', 0),
            },
        )
        session.commit()
        return job
    except ImportJobNotFoundError:
        session.rollback()
        raise_not_found('Import job not found')
    except ImportJobValidationError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Invalid import resolution',
        ) from exc

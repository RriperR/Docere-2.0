"""REST-роуты загрузки архивов пациентов."""

from __future__ import annotations

from contextlib import suppress
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, status, UploadFile
from sqlalchemy.orm import Session

from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.import_jobs.dtos import ImportJobDTO
from app.application.use_cases.import_jobs.errors import ImportJobNotFoundError, ImportJobValidationError
from app.application.use_cases.import_jobs.use_cases import CreateImportJobUseCase, GetImportJobUseCase
from app.infrastructure.adapters.queue.tasks import process_import_job
from app.infrastructure.adapters.repositories.import_jobs.sqlalchemy_import_job_repository import (
    SqlAlchemyImportJobRepositoryAdapter,
)
from app.infrastructure.adapters.storage.factory import get_file_storage
from app.presentation.rest.public.v1.archives.schemas import ImportJobResponseSchema
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
)
from app.presentation.webserver.http_errors import raise_not_found

router = APIRouter(prefix='/archives', tags=['archives'])
archive_file_dependency = File(...)


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


create_import_job_use_case_dependency = Depends(get_create_import_job_use_case)
get_import_job_use_case_dependency = Depends(get_import_job_use_case)


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
    content = file.file.read()
    try:
        job = use_case.execute(
            uploaded_by_user_id=current_user.id,
            original_filename=file.filename or 'archive.zip',
            content=content,
            content_type=file.content_type or 'application/zip',
        )
        session.commit()
        with suppress(Exception):
            process_import_job.delay(str(job.id))
        return job
    except ImportJobValidationError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='ZIP archive is required') from exc
    except Exception:
        session.rollback()
        raise


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

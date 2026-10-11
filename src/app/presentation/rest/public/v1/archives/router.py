"""REST-роуты загрузки архивов пациентов."""

from __future__ import annotations

from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, status, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.application.ports.import_jobs.document_bundle import UploadedDocument
from app.application.use_cases.auth.common.dtos import AuthenticatedUserDTO
from app.application.use_cases.import_jobs.documents import ReadImportSourceUseCase, UploadDocumentsUseCase
from app.application.use_cases.import_jobs.dtos import ImportJobDTO, ImportReviewDraftDTO
from app.application.use_cases.import_jobs.errors import (
    ImportJobDuplicateConfirmationRequiredError,
    ImportJobEventDateRequiredError,
    ImportJobNotFoundError,
    ImportJobValidationError,
    ImportReviewConflictError,
)
from app.application.use_cases.import_jobs.use_cases import (
    CreateImportJobUseCase,
    GetImportJobUseCase,
    ListImportJobsUseCase,
    ResolveImportJobUseCase,
    SaveImportReviewDraftUseCase,
)
from app.infrastructure.adapters.import_jobs.document_bundle import DocumentBundle
from app.infrastructure.adapters.import_jobs.factory import build_zip_archive_reader
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
from app.presentation.rest.public.v1.archives.events import router as events_router
from app.presentation.rest.public.v1.archives.schemas import (
    ImportJobResponseSchema,
    ImportReviewDraftResponseSchema,
    ResolveImportJobRequestSchema,
    SaveImportReviewDraftRequestSchema,
)
from app.presentation.rest.public.v1.records.dependencies import (
    current_authenticated_user_dependency,
    db_session_dependency,
)
from app.presentation.webserver.http_errors import raise_forbidden, raise_not_found, raise_payload_too_large

router = APIRouter(prefix='/archives', tags=['archives'])
router.include_router(events_router)
archive_file_dependency = File(None)
documents_dependency = File(None)
ai_requested_dependency = Form(False)
MAX_ARCHIVE_SIZE_MB = 200
MAX_ARCHIVE_SIZE_BYTES = MAX_ARCHIVE_SIZE_MB * 1024 * 1024


def _build_repository(session: Session) -> SqlAlchemyImportJobRepositoryAdapter:
    return SqlAlchemyImportJobRepositoryAdapter(session=session)


def get_create_import_job_use_case(session: Session = db_session_dependency) -> CreateImportJobUseCase:
    """Создать use case загрузки архива.

    Returns:
        Настроенный use case.
    """
    return CreateImportJobUseCase(
        repository=_build_repository(session),
        storage=get_file_storage(),
        audit_events=AuditEventRepositoryAdapter(session=session),
    )


def get_import_job_use_case(session: Session = db_session_dependency) -> GetImportJobUseCase:
    """Создать use case чтения ImportJob.

    Returns:
        Настроенный use case.
    """
    return GetImportJobUseCase(
        repository=_build_repository(session),
        medical_records=SqlAlchemyMedicalRecordRepositoryAdapter(session=session),
    )


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
        audit_events=AuditEventRepositoryAdapter(session=session),
    )


def get_save_import_review_draft_use_case(
    session: Session = db_session_dependency,
) -> SaveImportReviewDraftUseCase:
    """Создать use case сохранения черновика review.

    Returns:
        Настроенный use case сохранения черновика.
    """
    return SaveImportReviewDraftUseCase(repository=_build_repository(session))


create_import_job_use_case_dependency = Depends(get_create_import_job_use_case)
get_import_job_use_case_dependency = Depends(get_import_job_use_case)
list_import_jobs_use_case_dependency = Depends(get_list_import_jobs_use_case)
resolve_import_job_use_case_dependency = Depends(get_resolve_import_job_use_case)
save_import_review_draft_use_case_dependency = Depends(get_save_import_review_draft_use_case)


@router.post('/imports', response_model=ImportJobResponseSchema, status_code=status.HTTP_201_CREATED)
def create_import_job(
    request: Request,
    file: UploadFile | None = archive_file_dependency,
    files: list[UploadFile] | None = documents_dependency,
    ai_requested: bool = ai_requested_dependency,
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
    if current_user.role not in {'doctor', 'admin'}:
        raise_forbidden('Only doctors and admins can upload documents')
    if files:
        if file or len(files) > 100:
            raise HTTPException(422, 'Выберите ZIP либо отдельные документы')
        try:
            documents = tuple(
                UploadedDocument(f.filename or 'document', f.file.read(MAX_ARCHIVE_SIZE_BYTES + 1)) for f in files
            )
            job = UploadDocumentsUseCase(DocumentBundle(), use_case).execute(
                documents, current_user.id, request.state.request_id, ai_requested
            )
            session.commit()
            return job
        except ImportJobValidationError as exc:
            session.rollback()
            raise HTTPException(422, 'Допустимы PDF, PNG и JPEG; проверьте размеры файлов') from exc
    if file is None:
        raise HTTPException(422, 'Выберите документы')
    if file.size is not None and file.size > MAX_ARCHIVE_SIZE_BYTES:
        raise_payload_too_large(f'Archive exceeds maximum size {MAX_ARCHIVE_SIZE_MB} MB')
    content = file.file.read(MAX_ARCHIVE_SIZE_BYTES + 1)
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
            request_id=request.state.request_id,
            ai_requested=ai_requested,
        )
        session.commit()
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


@router.put('/imports/{job_id}/review-draft', response_model=ImportReviewDraftResponseSchema)
def save_import_review_draft(
    job_id: UUID,
    payload: SaveImportReviewDraftRequestSchema,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    use_case: SaveImportReviewDraftUseCase = save_import_review_draft_use_case_dependency,
    session: Session = db_session_dependency,
) -> ImportReviewDraftDTO:
    """Сохранить промежуточные решения review задания импорта.

    Returns:
        Сохраненный черновик и время его обновления.

    Raises:
        HTTPException: Если задание недоступно или больше не ожидает review.
    """
    if current_user.role not in {'doctor', 'admin'}:
        raise_forbidden('Only doctors and admins can review imports')
    try:
        draft = use_case.execute(
            job_id=job_id,
            actor_user_id=current_user.id,
            actor_role=current_user.role,
            decisions=[decision.model_dump(mode='json') for decision in payload.decisions],
            version=payload.version,
        )
        session.commit()
        return draft
    except ImportReviewConflictError as exc:
        session.rollback()
        raise HTTPException(409, 'Черновик изменился. Обновите данные, сохранив свои правки') from exc
    except ImportJobNotFoundError:
        session.rollback()
        raise_not_found('Import job not found')
    except ImportJobValidationError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Invalid import review draft',
        ) from exc


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
            version=payload.version,
        )
        session.commit()
        return job
    except ImportReviewConflictError as exc:
        session.rollback()
        raise HTTPException(409, 'Черновик изменился. Обновите данные, сохранив свои правки') from exc
    except ImportJobNotFoundError:
        session.rollback()
        raise_not_found('Import job not found')
    except ImportJobDuplicateConfirmationRequiredError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                'code': 'duplicate_confirmation_required',
                'group_id': exc.group_id,
            },
        ) from exc
    except ImportJobEventDateRequiredError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                'code': 'event_date_required',
                'group_id': exc.group_id,
            },
        ) from exc
    except ImportJobValidationError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Invalid import resolution',
        ) from exc


@router.get('/imports/{job_id}/files/{file_id}')
def read_import_source(
    job_id: UUID,
    file_id: str,
    current_user: AuthenticatedUserDTO = current_authenticated_user_dependency,
    session: Session = db_session_dependency,
) -> Response:
    """Вернуть исходник через API после проверки доступа к импорту.

    Returns:
        Документ с запретом кеширования.

    Raises:
        HTTPException: Черновик изменился во время операции.
    """
    if current_user.role not in {'doctor', 'admin'}:
        raise_forbidden('Документ недоступен')
    try:
        source = ReadImportSourceUseCase(
            _build_repository(session), get_file_storage(), build_zip_archive_reader()
        ).execute(job_id, file_id, current_user.id, current_user.role)
    except ImportReviewConflictError as exc:
        session.rollback()
        raise HTTPException(409, 'Черновик изменился. Обновите данные, сохранив свои правки') from exc
    except ImportJobNotFoundError:
        raise_not_found('Документ недоступен')
    return Response(
        source.content,
        media_type=source.mime_type,
        headers={
            'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
            'Content-Disposition': "inline; filename*=UTF-8''" + quote(source.filename),
        },
    )

"""Фоновые Celery-задачи."""

from collections.abc import Callable
from datetime import date
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.use_cases.import_jobs.extractor import ArchiveExtractionError, extract_import_draft
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
            report = extract_import_draft(
                archive_filename=job.original_filename or 'archive.zip',
                archive_content=archive_content,
            )
            _enrich_existing_matches(
                report=report,
                patient_repository=SqlAlchemyPatientCardRepositoryAdapter(session=session),
                requested_by_user_id=job.uploaded_by_user_id,
                requested_by_role=_user_role(session=session, user_id=job.uploaded_by_user_id),
            )
            repository.mark_needs_review(job_id=job.id, report_json=report)
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


def _enrich_existing_matches(
    *,
    report: dict[str, object],
    patient_repository: SqlAlchemyPatientCardRepositoryAdapter,
    requested_by_user_id: UUID,
    requested_by_role: str,
) -> None:
    patients = report.get('patients')
    if not isinstance(patients, list):
        return
    for patient in patients:
        if not isinstance(patient, dict):
            continue
        fio = patient.get('fio')
        if not isinstance(fio, str) or not fio.strip():
            patient['existing_matches'] = []
            continue
        date_of_birth = _parse_date(patient.get('date_of_birth'))
        matches = patient_repository.search_patient_passports(
            query=fio,
            date_of_birth=date_of_birth,
            requested_by_user_id=requested_by_user_id,
            requested_by_role=requested_by_role,
            limit=5,
        )
        patient['existing_matches'] = [
            {
                'id': str(match.patient.id),
                'fio': match.patient.fio,
                'date_of_birth': match.patient.date_of_birth.isoformat()
                if match.patient.date_of_birth is not None
                else None,
                'status': match.patient.status,
                'match_score': match.match_score,
                'match_type': _match_type(fio, date_of_birth, match.patient.fio, match.patient.date_of_birth),
            }
            for match in matches
        ]


def _match_type(
    fio: str,
    date_of_birth: date | None,
    matched_fio: str,
    matched_date_of_birth: date | None,
) -> str:
    if (
        fio.casefold() == matched_fio.casefold()
        and date_of_birth is not None
        and date_of_birth == matched_date_of_birth
    ):
        return 'exact'
    return 'fuzzy'


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _user_role(*, session: Session, user_id: UUID) -> str:
    role = session.scalar(select(UserRow.role).where(UserRow.id == user_id))
    if role is None:
        return 'doctor'
    return role.value

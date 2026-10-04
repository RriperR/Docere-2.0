"""Короткие транзакции захвата и завершения импорта с fencing token."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import update

from app.domain.entities.import_job import ImportJob, ImportJobStatus
from app.infrastructure.adapters.repositories.import_jobs.sqlalchemy_import_job_repository import (
    SqlAlchemyImportJobRepositoryAdapter,
)
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.medical_records.import_job import ImportJobRow
from app.infrastructure.db.session import get_session_factory

# Запас относительно hard time limit Celery (960 секунд). Worker должен быть остановлен
# до истечения lease; fencing token всё равно запрещает запись устаревшего результата.
IMPORT_LEASE_SECONDS = 1200


def claim_import(job_id: UUID, token: UUID) -> ImportJob | None:
    """Захватить только queued-задание.

    Args:
        job_id: Идентификатор задания.
        token: Уникальный идентификатор попытки обработки.

    Returns:
        Задание или None, если его уже обрабатывают.
    """
    with get_session_factory()() as session:
        row = session.scalars(
            update(ImportJobRow)
            .where(ImportJobRow.id == job_id, ImportJobRow.status == ImportJobStatus.QUEUED)
            .values(
                status=ImportJobStatus.RUNNING,
                processing_token=token,
                lease_expires_at=utc_now() + timedelta(seconds=IMPORT_LEASE_SECONDS),
                version=ImportJobRow.version + 1,
            )
            .returning(ImportJobRow),
        ).one_or_none()
        if row is None:
            return None
        job = SqlAlchemyImportJobRepositoryAdapter(session).get_job(
            job_id=job_id,
            requested_by_user_id=row.uploaded_by_user_id,
            requested_by_role='doctor',
        )
        session.commit()
        return job


def finish_import(job_id: UUID, token: UUID, status: ImportJobStatus, report: dict[str, object]) -> bool:
    """Записать результат, только если попытка всё ещё владеет заданием.

    Args:
        job_id: Идентификатор задания.
        token: Идентификатор попытки, получившей задание.
        status: Результирующий статус фоновой обработки.
        report: Черновик или описание ошибки.

    Returns:
        True, если результат принят.
    """
    with get_session_factory()() as session:
        updated = session.scalar(
            update(ImportJobRow)
            .where(
                ImportJobRow.id == job_id,
                ImportJobRow.status == ImportJobStatus.RUNNING,
                ImportJobRow.processing_token == token,
            )
            .values(
                status=status,
                report_json=report,
                processing_token=None,
                lease_expires_at=None,
                version=ImportJobRow.version + 1,
                finished_at=utc_now() if status == ImportJobStatus.FAILED else None,
            )
            .returning(ImportJobRow.id),
        )
        session.commit()
        return updated is not None

"""SQLAlchemy-репозиторий ImportJob."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.ports.repositories.import_jobs.port import ImportJobRepositoryPort
from app.domain.entities.import_job import ImportJob, ImportJobStatus
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.medical_records.import_job import ImportJobRow


class SqlAlchemyImportJobRepositoryAdapter(ImportJobRepositoryPort):
    """Репозиторий заданий импорта архивов."""

    def __init__(self, session: Session) -> None:
        """Инициализировать репозиторий.

        Args:
            session: Активная SQLAlchemy-сессия.
        """
        self._session = session

    def create_job(
        self,
        *,
        uploaded_by_user_id: UUID,
        original_filename: str,
        archive_storage_key: str,
        size_bytes: int,
    ) -> ImportJob:
        """Создать ImportJob в статусе queued.

        Returns:
            Созданное задание импорта.
        """
        row = ImportJobRow(
            uploaded_by_user_id=uploaded_by_user_id,
            status=ImportJobStatus.QUEUED,
            original_filename=original_filename,
            archive_storage_key=archive_storage_key,
            size_bytes=size_bytes,
            report_json={
                'message': 'Archive uploaded and queued for processing',
                'archive_storage_key': archive_storage_key,
                'original_filename': original_filename,
                'size_bytes': size_bytes,
            },
        )
        self._session.add(row)
        self._session.flush()
        return self._to_domain(row)

    def get_job(self, *, job_id: UUID, requested_by_user_id: UUID, requested_by_role: str) -> ImportJob | None:
        """Вернуть ImportJob, если он доступен пользователю.

        Returns:
            Задание импорта или ``None``.
        """
        row = self._session.get(ImportJobRow, job_id)
        if row is None:
            return None
        if requested_by_role != 'admin' and row.uploaded_by_user_id != requested_by_user_id:
            return None
        return self._to_domain(row)

    def list_jobs(self, *, requested_by_user_id: UUID, requested_by_role: str, limit: int) -> tuple[ImportJob, ...]:
        """Return accessible ImportJob rows, newest first."""
        statement = select(ImportJobRow).order_by(ImportJobRow.created_at.desc()).limit(limit)
        if requested_by_role != 'admin':
            statement = statement.where(ImportJobRow.uploaded_by_user_id == requested_by_user_id)
        rows = self._session.scalars(statement).all()
        return tuple(self._to_domain(row) for row in rows)

    def mark_running(self, *, job_id: UUID) -> ImportJob | None:
        """Перевести ImportJob в running.

        Returns:
            Обновленное задание или ``None``.
        """
        row = self._session.get(ImportJobRow, job_id)
        if row is None:
            return None
        row.status = ImportJobStatus.RUNNING
        self._session.flush()
        return self._to_domain(row)

    def mark_needs_review(self, *, job_id: UUID, report_json: dict[str, object]) -> ImportJob | None:
        """Перевести ImportJob в needs_review.

        Returns:
            Обновленное задание или ``None``.
        """
        row = self._session.get(ImportJobRow, job_id)
        if row is None:
            return None
        row.status = ImportJobStatus.NEEDS_REVIEW
        row.report_json = report_json
        self._session.flush()
        return self._to_domain(row)

    def mark_completed(self, *, job_id: UUID, report_json: dict[str, object]) -> ImportJob | None:
        """Перевести ImportJob в completed.

        Returns:
            Обновленное задание или ``None``.
        """
        row = self._session.get(ImportJobRow, job_id)
        if row is None:
            return None
        row.status = ImportJobStatus.COMPLETED
        row.report_json = report_json
        row.finished_at = utc_now()
        self._session.flush()
        return self._to_domain(row)

    def mark_completed_with_warnings(self, *, job_id: UUID, report_json: dict[str, object]) -> ImportJob | None:
        """Перевести ImportJob в completed_with_warnings.

        Returns:
            Обновленное задание или ``None``.
        """
        row = self._session.get(ImportJobRow, job_id)
        if row is None:
            return None
        row.status = ImportJobStatus.COMPLETED_WITH_WARNINGS
        row.report_json = report_json
        row.finished_at = utc_now()
        self._session.flush()
        return self._to_domain(row)

    def mark_failed(self, *, job_id: UUID, report_json: dict[str, object]) -> ImportJob | None:
        """Перевести ImportJob в failed.

        Returns:
            Обновленное задание или ``None``.
        """
        row = self._session.get(ImportJobRow, job_id)
        if row is None:
            return None
        row.status = ImportJobStatus.FAILED
        row.report_json = report_json
        row.finished_at = utc_now()
        self._session.flush()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: ImportJobRow) -> ImportJob:
        return ImportJob(
            id=row.id,
            uploaded_by_user_id=row.uploaded_by_user_id,
            status=row.status,
            original_filename=row.original_filename,
            archive_storage_key=row.archive_storage_key,
            size_bytes=row.size_bytes,
            report_json=row.report_json,
            created_at=row.created_at,
            finished_at=row.finished_at,
        )

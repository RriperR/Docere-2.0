"""SQLAlchemy-репозиторий ImportJob."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.application.ports.repositories.import_jobs.port import ImportJobRepositoryPort
from app.domain.entities.import_job import ImportJob, ImportJobProgress, ImportJobStatus
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.import_ai import ImportAiDocumentRow, ImportAiRunRow
from app.infrastructure.db.models.import_dispatch import ImportDispatchRow
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
        request_id: str | None = None,
        ai_requested: bool = False,
    ) -> ImportJob:
        """Атомарно создать ImportJob в статусе queued и намерение отправить его обработчику.

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
                'ai_requested': ai_requested,
                'message': 'Archive uploaded and queued for processing',
                'archive_storage_key': archive_storage_key,
                'original_filename': original_filename,
                'size_bytes': size_bytes,
            },
        )
        self._session.add(row)
        self._session.flush()
        self._session.add(ImportDispatchRow(job_id=row.id, request_id=request_id))
        self._session.flush()
        return self._to_domain(row)

    def get_job(self, *, job_id: UUID, requested_by_user_id: UUID, requested_by_role: str) -> ImportJob | None:
        """Вернуть ImportJob, если он доступен пользователю.

        Returns:
            Задание импорта или ``None``.
        """
        if requested_by_role not in {'doctor', 'admin'}:
            return None
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

    def mark_completed(self, *, job_id: UUID, report_json: dict[str, object]) -> ImportJob | None:
        """Перевести ImportJob в completed.

        Returns:
            Обновленное задание или ``None``.
        """
        row = self._session.get(ImportJobRow, job_id)
        if row is None:
            return None
        self._cancel_ai(job_id)
        row.status = ImportJobStatus.COMPLETED
        row.version += 1
        row.report_json = report_json
        row.review_decisions_json = None
        row.review_updated_at = None
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
        self._cancel_ai(job_id)
        row.status = ImportJobStatus.COMPLETED_WITH_WARNINGS
        row.version += 1
        row.report_json = report_json
        row.review_decisions_json = None
        row.review_updated_at = None
        row.finished_at = utc_now()
        self._session.flush()
        return self._to_domain(row)

    def save_review_draft(self, *, job_id: UUID, decisions: list[dict[str, object]]) -> ImportJob | None:
        """Сохранить промежуточные решения review для ImportJob.

        Returns:
            Обновленное задание или ``None``.
        """
        row = self._session.get(ImportJobRow, job_id)
        if row is None:
            return None
        row.version += 1
        row.review_decisions_json = decisions or None
        row.review_updated_at = utc_now() if decisions else None
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
            review_decisions=tuple(row.review_decisions_json or ()),
            review_updated_at=row.review_updated_at,
            created_at=row.created_at,
            finished_at=row.finished_at,
            version=row.version,
        )

    def get_progress(
        self,
        *,
        job_id: UUID,
        requested_by_user_id: UUID,
        requested_by_role: str,
    ) -> ImportJobProgress | None:
        """Прочитать лёгкую проекцию статуса с проверкой доступа.

        Returns:
            Статус и версия или None для недоступного задания.
        """
        statement = select(ImportJobRow.id, ImportJobRow.status, ImportJobRow.version).where(ImportJobRow.id == job_id)
        if requested_by_role != 'admin':
            statement = statement.where(ImportJobRow.uploaded_by_user_id == requested_by_user_id)
        row = self._session.execute(statement).one_or_none()
        return ImportJobProgress(id=row.id, status=row.status, version=row.version) if row is not None else None

    def lock_job(self, *, job_id: UUID, requested_by_user_id: UUID, requested_by_role: str) -> ImportJob | None:
        """Захватить строку до конца транзакции и повторно проверить доступ.

        Returns:
            Доступное задание либо None.
        """
        row = self._session.scalar(
            select(ImportJobRow)
            .where(ImportJobRow.id == job_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if row is None or (requested_by_role != 'admin' and row.uploaded_by_user_id != requested_by_user_id):
            return None
        return self._to_domain(row)

    def _cancel_ai(self, job_id: UUID) -> None:
        ids = self._session.scalars(
            update(ImportAiRunRow)
            .where(ImportAiRunRow.job_id == job_id, ImportAiRunRow.status.in_(['queued', 'running']))
            .values(status='cancelled', processing_token=None, finished_at=utc_now())
            .returning(ImportAiRunRow.id)
        ).all()
        if ids:
            self._session.execute(
                update(ImportAiDocumentRow)
                .where(ImportAiDocumentRow.run_id.in_(ids), ImportAiDocumentRow.status == 'queued')
                .values(status='cancelled', error_code='cancelled')
            )

    def replace_review(self, job_id: UUID, report: dict[str, object], decisions: list[dict[str, object]]) -> ImportJob:
        """Сохранить перегруппировку, сохранив стабильные идентификаторы файлов.

        Returns:
            Обновлённый импорт.

        Raises:
            ValueError: Исходный импорт отсутствует.
        """
        row = self._session.get(ImportJobRow, job_id)
        if row is None:
            raise ValueError('Import job not found')
        row.report_json = report
        row.review_decisions_json = decisions
        row.review_updated_at = utc_now()
        row.version += 1
        self._session.flush()
        return self._to_domain(row)

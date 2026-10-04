"""Контракт репозитория ImportJob."""

from __future__ import annotations

from uuid import UUID

from app.domain.entities.import_job import ImportJob, ImportJobProgress


class ImportJobRepositoryPort:
    """Порт создания и обновления заданий импорта."""

    def create_job(
        self,
        *,
        uploaded_by_user_id: UUID,
        original_filename: str,
        archive_storage_key: str,
        size_bytes: int,
        request_id: str | None = None,
    ) -> ImportJob:
        """Атомарно создать ImportJob в статусе queued и намерение отправить его обработчику."""
        raise NotImplementedError

    def get_job(self, *, job_id: UUID, requested_by_user_id: UUID, requested_by_role: str) -> ImportJob | None:
        """Вернуть ImportJob, если он доступен пользователю."""
        raise NotImplementedError

    def list_jobs(self, *, requested_by_user_id: UUID, requested_by_role: str, limit: int) -> tuple[ImportJob, ...]:
        """Return accessible ImportJob rows."""
        raise NotImplementedError

    def mark_completed(self, *, job_id: UUID, report_json: dict[str, object]) -> ImportJob | None:
        """Перевести ImportJob в completed."""
        raise NotImplementedError

    def mark_completed_with_warnings(self, *, job_id: UUID, report_json: dict[str, object]) -> ImportJob | None:
        """Перевести ImportJob в completed_with_warnings."""
        raise NotImplementedError

    def save_review_draft(self, *, job_id: UUID, decisions: list[dict[str, object]]) -> ImportJob | None:
        """Сохранить промежуточные решения review для ImportJob."""
        raise NotImplementedError

    def get_progress(
        self,
        *,
        job_id: UUID,
        requested_by_user_id: UUID,
        requested_by_role: str,
    ) -> ImportJobProgress | None:
        """Вернуть доступный статус, не загружая медицинский отчёт."""
        raise NotImplementedError

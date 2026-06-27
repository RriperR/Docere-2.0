"""ORM-модель задания импорта архива."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, func, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.entities.import_job import ImportJobStatus
from app.infrastructure.db.base import Base
from app.infrastructure.db.models._enums import enum_values


class ImportJobRow(Base):
    """ORM-представление таблицы `import_jobs`."""

    __tablename__ = 'import_jobs'

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    uploaded_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), index=True)
    status: Mapped[ImportJobStatus] = mapped_column(
        Enum(
            ImportJobStatus,
            name='import_job_status',
            native_enum=True,
            validate_strings=True,
            values_callable=enum_values,
        ),
        default=ImportJobStatus.QUEUED,
    )
    original_filename: Mapped[str | None] = mapped_column(String(length=255), nullable=True)
    archive_storage_key: Mapped[str | None] = mapped_column(String(length=512), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    report_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    review_decisions_json: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)
    review_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

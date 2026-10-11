"""Персистентные AI-запуски и результаты выбранных документов."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, func, Index, JSON, String, text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class ImportAiRunRow(Base):
    """Запуск одновременно хранит транзакционное намерение доставки."""

    __tablename__ = 'import_ai_runs'
    __table_args__ = (
        UniqueConstraint('job_id', 'idempotency_key', name='uq_import_ai_run_key'),
        Index(
            'uq_import_ai_active_job',
            'job_id',
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
        Index('ix_import_ai_delivery', 'status', 'next_delivery_at'),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey('import_jobs.id'), nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey('users.id'), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    selection_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='queued')
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_delivery_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivery_attempts: Mapped[int] = mapped_column(default=0, server_default='0')
    processing_token: Mapped[UUID | None] = mapped_column(Uuid)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    options_json: Mapped[dict[str, object]] = mapped_column(JSON().with_variant(JSONB(), 'postgresql'), nullable=False)


class ImportAiDocumentRow(Base):
    """Независимый результат файла; завершённые документы сохраняются при redelivery."""

    __tablename__ = 'import_ai_documents'
    run_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey('import_ai_runs.id'), primary_key=True)
    file_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='queued')
    page_count: Mapped[int] = mapped_column(default=0, server_default='0')
    checksum: Mapped[str | None] = mapped_column(String(64))
    result_json: Mapped[dict[str, object]] = mapped_column(JSON().with_variant(JSONB(), 'postgresql'), default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64))
    usage_json: Mapped[dict[str, int]] = mapped_column(JSON, default=dict)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

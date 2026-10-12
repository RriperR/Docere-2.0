"""Личные AI-сводки с транзакционным намерением фоновой доставки."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, func, Index, JSON, String, text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class CaseSummaryRunRow(Base):
    """Снимок источников, состояние документов и lease текущей попытки."""

    __tablename__ = 'case_summary_runs'
    __table_args__ = (
        UniqueConstraint('case_id', 'user_id', 'idempotency_key', name='uq_case_summary_key'),
        Index(
            'uq_case_summary_active',
            'case_id',
            'user_id',
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
        Index('ix_case_summary_delivery', 'status', 'next_delivery_at'),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey('clinical_cases.id'), nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey('users.id'), nullable=False)
    idempotency_key: Mapped[UUID] = mapped_column(Uuid, nullable=False)
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
    options_json: Mapped[dict[str, object]] = mapped_column(JSON().with_variant(JSONB(), 'postgresql'))
    sources_json: Mapped[list[dict[str, str]]] = mapped_column(JSON().with_variant(JSONB(), 'postgresql'))
    documents_json: Mapped[list[dict[str, object]]] = mapped_column(JSON().with_variant(JSONB(), 'postgresql'))

"""Транзакционное намерение доставить импорт обработчику Celery."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models._time import utc_now


class ImportDispatchRow(Base):
    """Одна запись на импорт; повторная доставка разрешена до захвата задания."""

    __tablename__ = 'import_dispatch'

    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey('import_jobs.id', ondelete='CASCADE'),
        primary_key=True,
    )
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    attempts: Mapped[int] = mapped_column(default=0, server_default='0')

"""ORM-модель события аудита."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, func, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class AuditEventRow(Base):
    """ORM-представление таблицы `audit_events`."""

    __tablename__ = 'audit_events'

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), nullable=True)
    event_type: Mapped[str] = mapped_column(String(length=128), index=True)
    entity_type: Mapped[str] = mapped_column(String(length=128), index=True)
    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), index=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

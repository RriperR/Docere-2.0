"""ORM-модель комментариев к медицинской записи."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models._time import utc_now


class RecordCommentRow(Base):
    """ORM-представление таблицы `record_comments`."""

    __tablename__ = 'record_comments'

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    record_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('medical_records.id'), index=True)
    author_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey('users.id'), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

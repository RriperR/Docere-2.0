"""Таблицы клинических случаев и их участников."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, func, Index, Integer, JSON, String, Text, text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models._time import utc_now


class ClinicalCaseRow(Base):
    """Корень разбора и версия для конкурентных изменений."""

    __tablename__ = 'clinical_cases'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    patient_id: Mapped[UUID] = mapped_column(ForeignKey('patient_passports.id'))
    coordinator_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(255))
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default='draft', index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    previous_case_id: Mapped[UUID | None] = mapped_column(ForeignKey('clinical_cases.id'), nullable=True)
    published_record_id: Mapped[UUID | None] = mapped_column(ForeignKey('medical_records.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseMaterialRow(Base):
    """Ссылка на существующий материал без копирования документов."""

    __tablename__ = 'case_materials'
    case_id: Mapped[UUID] = mapped_column(ForeignKey('clinical_cases.id'), primary_key=True)
    record_id: Mapped[UUID] = mapped_column(ForeignKey('medical_records.id'), primary_key=True)


class CaseMemberRow(Base):
    """Единственное участие пользователя в каждом случае."""

    __tablename__ = 'case_members'
    __table_args__ = (UniqueConstraint('share_request_id', name='uq_case_member_share'),)
    case_id: Mapped[UUID] = mapped_column(ForeignKey('clinical_cases.id'), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default='pending')
    share_request_id: Mapped[UUID | None] = mapped_column(ForeignKey('record_share_requests.id'), nullable=True)
    read_sequence: Mapped[int] = mapped_column(Integer, default=0)


class CaseMessageRow(Base):
    """Append-only сообщения обсуждения."""

    __tablename__ = 'case_messages'
    __table_args__ = (UniqueConstraint('case_id', 'author_id', 'idempotency_key', name='uq_case_message_retry'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey('clinical_cases.id'), index=True)
    author_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    body: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[UUID] = mapped_column(Uuid)
    sequence: Mapped[int] = mapped_column(Integer)
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey('case_messages.id'), nullable=True)
    record_id: Mapped[UUID | None] = mapped_column(ForeignKey('medical_records.id'), nullable=True)
    attachment_id: Mapped[UUID | None] = mapped_column(ForeignKey('file_attachments.id'), nullable=True)
    opinion_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OpinionRequestRow(Base):
    """Адресат, вопрос и результат адресного запроса."""

    __tablename__ = 'case_opinions'
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey('clinical_cases.id'), index=True)
    requester_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    assignee_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default='open')
    record_id: Mapped[UUID | None] = mapped_column(ForeignKey('medical_records.id'), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    response_message_id: Mapped[UUID | None] = mapped_column(ForeignKey('case_messages.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseEventRow(Base):
    """Журнал доменных действий, пригодный для доставки через outbox."""

    __tablename__ = 'case_events'
    __table_args__ = (
        UniqueConstraint('case_id', 'sequence', name='uq_case_event_sequence'),
        Index(
            'ix_case_event_pending',
            'next_attempt_at',
            postgresql_where=text('delivered_at IS NULL'),
            sqlite_where=text('delivered_at IS NULL'),
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey('clinical_cases.id'), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    subject_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    recipients: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB(), 'postgresql'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseConclusionRow(Base):
    """Версии итога разбора; обновление создаёт новую строку."""

    __tablename__ = 'case_conclusions'
    __table_args__ = (UniqueConstraint('case_id', 'number', name='uq_case_conclusion_version'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(ForeignKey('clinical_cases.id'), index=True)
    number: Mapped[int] = mapped_column(Integer)
    author_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'))
    summary: Mapped[str] = mapped_column(Text)
    findings: Mapped[str] = mapped_column(Text)
    next_actions: Mapped[str] = mapped_column(Text)
    source_ids: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB(), 'postgresql'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseNotificationRow(Base):
    """Уведомление содержит только ссылку на событие, без клинического текста."""

    __tablename__ = 'case_notifications'
    __table_args__ = (UniqueConstraint('event_id', 'recipient_id', name='uq_case_notification_delivery'),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(ForeignKey('case_events.id'))
    recipient_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseDiscussionReadRow(Base):
    """Позиция прочтения обсуждения для координатора и участников."""

    __tablename__ = 'case_discussion_reads'
    case_id: Mapped[UUID] = mapped_column(ForeignKey('clinical_cases.id'), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey('users.id'), primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0)

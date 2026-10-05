"""Таблицы клинических случаев и их участников."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, func, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


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

"""SQLAlchemy read-model административной оперативной сводки."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session
from sqlalchemy.sql.elements import ColumnElement

from app.application.ports.repositories.admin_dashboard.dtos import (
    AdminArchiveMetricsDTO,
    AdminDashboardSummaryDTO,
    AdminSharingMetricsDTO,
    AdminUserMetricsDTO,
)
from app.application.ports.repositories.admin_dashboard.port import AdminDashboardRepositoryPort
from app.domain.entities.import_job import ImportJobStatus
from app.infrastructure.db.models.auth.user import UserRole, UserRow, UserStatus
from app.infrastructure.db.models.medical_records.import_job import ImportJobRow
from app.infrastructure.db.models.medical_records.patient_passport import PatientPassportRow
from app.infrastructure.db.models.medical_records.record_share import RecordShareRequestRow, RecordShareStatusRow


class SqlAlchemyAdminDashboardRepositoryAdapter(AdminDashboardRepositoryPort):
    """Собрать административные счетчики из SQL read-model."""

    def __init__(self, session: Session) -> None:
        """Инициализировать адаптер.

        Args:
            session: Активная SQLAlchemy-сессия.
        """
        self._session = session

    def get_summary(self) -> AdminDashboardSummaryDTO:
        """Вернуть актуальные системные счетчики.

        Returns:
            Агрегированная административная сводка.
        """
        users_total = self._count(UserRow.id)
        active_share_condition = or_(
            RecordShareRequestRow.expires_at.is_(None),
            RecordShareRequestRow.expires_at > datetime.now(UTC),
        )
        return AdminDashboardSummaryDTO(
            users=AdminUserMetricsDTO(
                total=users_total,
                active=self._count(UserRow.id, UserRow.status == UserStatus.ACTIVE),
                blocked=self._count(UserRow.id, UserRow.status == UserStatus.BLOCKED),
                doctors=self._count(UserRow.id, UserRow.role == UserRole.DOCTOR),
                patients=self._count(UserRow.id, UserRow.role == UserRole.PATIENT),
                admins=self._count(UserRow.id, UserRow.role == UserRole.ADMIN),
            ),
            patient_cards_total=self._count(PatientPassportRow.id),
            archives=AdminArchiveMetricsDTO(
                total=self._count(ImportJobRow.id),
                processing=self._count(
                    ImportJobRow.id,
                    ImportJobRow.status.in_((ImportJobStatus.QUEUED, ImportJobStatus.RUNNING)),
                ),
                needs_review=self._count(ImportJobRow.id, ImportJobRow.status == ImportJobStatus.NEEDS_REVIEW),
                failed=self._count(ImportJobRow.id, ImportJobRow.status == ImportJobStatus.FAILED),
                completed=self._count(
                    ImportJobRow.id,
                    ImportJobRow.status.in_(
                        (ImportJobStatus.COMPLETED, ImportJobStatus.COMPLETED_WITH_WARNINGS),
                    ),
                ),
            ),
            sharing=AdminSharingMetricsDTO(
                pending_requests=self._count(
                    RecordShareRequestRow.id,
                    RecordShareRequestRow.status == RecordShareStatusRow.PENDING,
                    active_share_condition,
                ),
                active_requests=self._count(
                    RecordShareRequestRow.id,
                    RecordShareRequestRow.status == RecordShareStatusRow.ACCEPTED,
                    active_share_condition,
                ),
            ),
        )

    def _count(self, column: InstrumentedAttribute[Any], *conditions: ColumnElement[bool]) -> int:
        value = self._session.scalar(select(func.count(column)).where(*conditions))
        return int(value or 0)

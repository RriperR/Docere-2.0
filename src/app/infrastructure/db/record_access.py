"""Единый предикат актуальности ACL, включая роль и участие в случае."""

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.auth.user import UserRole, UserRow, UserStatus
from app.infrastructure.db.models.clinical_cases import CaseMemberRow, ClinicalCaseRow
from app.infrastructure.db.models.medical_records.user_record_link import UserRecordLinkRow


def active_record_access() -> ColumnElement[bool]:
    """Исключить просроченные права и права случая после утраты роли или членства.

    Returns:
        SQL-предикат срока права и действующего членства/роли для источников случая.
    """
    coordinator = aliased(UserRow)
    recipient = aliased(UserRow)
    valid_case = exists(
        select(CaseMemberRow.case_id)
        .join(ClinicalCaseRow, ClinicalCaseRow.id == CaseMemberRow.case_id)
        .join(coordinator, coordinator.id == ClinicalCaseRow.coordinator_id)
        .join(recipient, recipient.id == CaseMemberRow.user_id)
        .where(
            CaseMemberRow.case_id == UserRecordLinkRow.clinical_case_id,
            CaseMemberRow.user_id == UserRecordLinkRow.user_id,
            CaseMemberRow.status == 'accepted',
            coordinator.role == UserRole.DOCTOR,
            coordinator.status == UserStatus.ACTIVE,
            recipient.role == UserRole.DOCTOR,
            recipient.status == UserStatus.ACTIVE,
        )
    )
    return and_(
        or_(UserRecordLinkRow.expires_at.is_(None), UserRecordLinkRow.expires_at > utc_now()),
        or_(UserRecordLinkRow.clinical_case_id.is_(None), valid_case),
    )

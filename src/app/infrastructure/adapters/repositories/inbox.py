"""Объединение актуальных задач без дополнительной таблицы уведомлений."""

from uuid import UUID

from sqlalchemy import func, literal, or_, select, union_all
from sqlalchemy.orm import Session

from app.application.use_cases.inbox.dtos import TaskCandidate, TaskKind
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.auth.user import UserRow
from app.infrastructure.db.models.clinical_cases import CaseEventRow, CaseMemberRow, ClinicalCaseRow, OpinionRequestRow
from app.infrastructure.db.models.medical_records.import_job import ImportJobRow
from app.infrastructure.db.models.medical_records.record_share import RecordShareRequestRow


class SqlAlchemyInboxRepository:
    """Серверная сортировка и ограниченная загрузка задач адресата."""

    def __init__(self, session: Session) -> None:
        """Привязать выборку к текущей транзакции.

        Args:
            session: Транзакционная SQLAlchemy-сессия.
        """
        self.session = session

    def candidates(self, user_id: UUID, kind: TaskKind | None, offset: int, limit: int) -> list[TaskCandidate]:
        """Выбрать кандидатов с условиями адресата, срока и состояния.

        Args:
            user_id: Адресат задачи или владелец импорта.
            kind: Тип задачи или все типы.
            offset: Смещение кандидатов.
            limit: Максимальный размер порции.

        Returns:
            Задачи в порядке даты и устойчивого вторичного ключа.
        """
        invites = (
            select(
                literal('invitation').label('kind'),
                CaseMemberRow.case_id.label('id'),
                CaseMemberRow.case_id.label('case_id'),
                UserRow.fio.label('actor_name'),
                select(func.max(CaseEventRow.created_at))
                .where(
                    CaseEventRow.case_id == CaseMemberRow.case_id,
                    CaseEventRow.subject_id == user_id,
                    CaseEventRow.event_type == 'invitation',
                )
                .correlate(CaseMemberRow)
                .scalar_subquery()
                .label('created_at'),
                literal(None).label('description'),
            )
            .join(ClinicalCaseRow, ClinicalCaseRow.id == CaseMemberRow.case_id)
            .join(UserRow, UserRow.id == ClinicalCaseRow.coordinator_id)
            .where(
                CaseMemberRow.user_id == user_id, CaseMemberRow.status == 'pending', ClinicalCaseRow.status == 'active'
            )
        )
        opinions = (
            select(
                literal('opinion_requested'),
                OpinionRequestRow.id,
                OpinionRequestRow.case_id,
                UserRow.fio,
                OpinionRequestRow.created_at,
                literal(None),
            )
            .join(UserRow, UserRow.id == OpinionRequestRow.requester_id)
            .join(ClinicalCaseRow, ClinicalCaseRow.id == OpinionRequestRow.case_id)
            .where(
                OpinionRequestRow.assignee_id == user_id,
                OpinionRequestRow.status == 'open',
                ClinicalCaseRow.status == 'active',
            )
        )
        shares = (
            select(
                literal('share_request'),
                RecordShareRequestRow.id,
                literal(None),
                UserRow.fio,
                RecordShareRequestRow.created_at,
                literal(None),
            )
            .join(UserRow, UserRow.id == RecordShareRequestRow.from_user_id)
            .where(
                RecordShareRequestRow.to_user_id == user_id,
                RecordShareRequestRow.status == 'pending',
                RecordShareRequestRow.clinical_case_id.is_(None),
                or_(RecordShareRequestRow.expires_at.is_(None), RecordShareRequestRow.expires_at > utc_now()),
            )
        )
        imports = select(
            literal('import_review'),
            ImportJobRow.id,
            literal(None),
            literal(None),
            ImportJobRow.created_at,
            ImportJobRow.original_filename,
        ).where(ImportJobRow.uploaded_by_user_id == user_id, ImportJobRow.status == 'needs_review')
        tasks = union_all(invites, opinions, shares, imports).subquery()
        query = select(tasks)
        if kind:
            query = query.where(tasks.c.kind == kind)
        rows = self.session.execute(
            query.order_by(tasks.c.created_at.desc(), tasks.c.kind, tasks.c.id).offset(offset).limit(limit)
        )
        return [
            TaskCandidate(row.kind, row.id, row.case_id, row.actor_name, row.created_at, row.description)
            for row in rows
        ]

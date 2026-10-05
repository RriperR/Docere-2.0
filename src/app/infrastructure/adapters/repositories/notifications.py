"""SQLAlchemy-реализация входящих уведомлений."""

from uuid import UUID

from sqlalchemy import exists, func, or_, select, union_all, update
from sqlalchemy.orm import Session

from app.application.notifications import AttentionTask, Notification
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.clinical_cases import (
    CaseEventRow,
    CaseMemberRow,
    CaseNotificationRow,
    ClinicalCaseRow,
    OpinionRequestRow,
)


class SqlAlchemyNotificationRepository:
    """Пагинированные входящие события и отметки прочтения."""

    def __init__(self, session: Session) -> None:
        """Инициализировать текущей транзакционной сессией.

        Args:
            session: Текущая транзакционная сессия.
        """
        self.session = session

    def list_notifications(self, user_id: UUID, offset: int, limit: int) -> tuple[list[Notification], int]:
        """Выбрать только уведомления адресата.

        Args:
            user_id: Текущий пользователь.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.

        Returns:
            Результат сценария в контексте текущего пользователя.
        """
        statement = (
            select(CaseNotificationRow, CaseEventRow)
            .join(CaseEventRow, CaseEventRow.id == CaseNotificationRow.event_id)
            .where(CaseNotificationRow.recipient_id == user_id)
        )
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = self.session.execute(
            statement.order_by(CaseNotificationRow.created_at.desc(), CaseNotificationRow.id)
            .offset(offset)
            .limit(limit)
        )
        return [
            Notification(n.id, e.event_type, e.case_id, e.subject_id, n.created_at, n.read_at) for n, e in rows
        ], total

    def counts(self, user_id: UUID) -> tuple[int, int, int]:
        """Посчитать собственные события без раскрытия медицинского содержимого.

        Args:
            user_id: Текущий пользователь.

        Returns:
            Результат сценария в контексте текущего пользователя.
        """
        total = (
            self.session.scalar(
                select(func.count()).select_from(CaseNotificationRow).where(CaseNotificationRow.recipient_id == user_id)
            )
            or 0
        )
        unread = (
            self.session.scalar(
                select(func.count())
                .select_from(CaseNotificationRow)
                .where(CaseNotificationRow.recipient_id == user_id, CaseNotificationRow.read_at.is_(None))
            )
            or 0
        )
        activity = (
            self.session.scalar(
                select(func.coalesce(func.sum(ClinicalCaseRow.sequence), 0)).where(
                    or_(
                        ClinicalCaseRow.coordinator_id == user_id,
                        exists().where(
                            CaseMemberRow.case_id == ClinicalCaseRow.id,
                            CaseMemberRow.user_id == user_id,
                            CaseMemberRow.status.in_(['pending', 'accepted']),
                        ),
                    )
                )
            )
            or 0
        )
        return total, unread, activity

    def read(self, user_id: UUID, notification_id: UUID | None) -> bool:
        """Идемпотентно отметить одно или все собственные уведомления.

        Args:
            user_id: Текущий пользователь.
            notification_id: Параметр операции.

        Returns:
            Результат сценария в контексте текущего пользователя.
        """
        if notification_id:
            row = self.session.scalar(
                select(CaseNotificationRow).where(
                    CaseNotificationRow.id == notification_id, CaseNotificationRow.recipient_id == user_id
                )
            )
            if row is None:
                return False
            if row.read_at is None:
                row.read_at = utc_now()
        else:
            self.session.execute(
                update(CaseNotificationRow)
                .where(CaseNotificationRow.recipient_id == user_id, CaseNotificationRow.read_at.is_(None))
                .values(read_at=utc_now())
            )
        return True

    def attention(self, user_id: UUID, offset: int, limit: int) -> tuple[list[AttentionTask], int]:
        """Получить идентификаторы собственных задач, не выбирая клинический текст.

        Args:
            user_id: Текущий пользователь.
            offset: Число пропускаемых элементов.
            limit: Размер страницы.

        Returns:
            Результат сценария в контексте текущего пользователя.
        """
        from sqlalchemy import literal

        invites = select(
            CaseMemberRow.case_id.label('case_id'),
            CaseMemberRow.case_id.label('subject_id'),
            literal('invitation').label('event_type'),
        ).where(CaseMemberRow.user_id == user_id, CaseMemberRow.status == 'pending')
        opinions = select(
            OpinionRequestRow.case_id.label('case_id'),
            OpinionRequestRow.id.label('subject_id'),
            literal('opinion_requested').label('event_type'),
        ).where(OpinionRequestRow.assignee_id == user_id, OpinionRequestRow.status == 'open')
        tasks = union_all(invites, opinions).subquery()
        total = self.session.scalar(select(func.count()).select_from(tasks)) or 0
        rows = self.session.execute(
            select(tasks).order_by(tasks.c.case_id, tasks.c.subject_id).offset(offset).limit(limit)
        )
        return [AttentionTask(row.case_id, row.subject_id, row.event_type) for row in rows], total

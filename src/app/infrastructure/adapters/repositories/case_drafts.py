"""SQLAlchemy-хранение личных форм с семидневным сроком жизни."""

from datetime import datetime, UTC
from typing import cast
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.case_drafts import CaseDraftContent, CaseWorkDraft, DraftKind
from app.infrastructure.db.models.clinical_cases import CaseWorkDraftRow


def _optional_id(value: object) -> UUID | None:
    return UUID(str(value)) if value else None


class SqlAlchemyCaseDraftRepository:
    """Хранение внутри транзакции под блокировкой корня случая."""

    def __init__(self, session: Session) -> None:
        """Связать адаптер с текущей транзакцией.

        Args:
            session: SQLAlchemy-сессия; commit принадлежит HTTP-границе.
        """
        self.session = session

    def get(self, case_id: UUID, user_id: UUID, kind: DraftKind, now: datetime) -> CaseWorkDraft | None:
        """Прочитать только личную форму и удалить истёкший текст.

        Args:
            case_id: Клинический случай.
            user_id: Автор формы.
            kind: Вид незавершённой формы.
            now: Время проверки срока.

        Returns:
            Неистёкшая форма или None.
        """
        row = self.session.get(CaseWorkDraftRow, (case_id, user_id, kind))
        if row is None:
            return None
        if row.expires_at.replace(tzinfo=UTC) <= now:
            self.session.delete(row)
            self.session.flush()
            return None
        value = row.content
        content = CaseDraftContent(
            text=str(value.get('text', '')),
            findings=str(value.get('findings', '')),
            next_actions=str(value.get('next_actions', '')),
            record_ids=tuple(UUID(str(item)) for item in cast(list[str], value.get('record_ids', []))),
            parent_id=_optional_id(value.get('parent_id')),
            opinion_id=_optional_id(value.get('opinion_id')),
            assignee_id=_optional_id(value.get('assignee_id')),
            attachment_id=_optional_id(value.get('attachment_id')),
            idempotency_key=_optional_id(value.get('idempotency_key')),
        )
        return CaseWorkDraft(case_id, user_id, kind, row.version, content, row.updated_at, row.expires_at)

    def save(self, draft: CaseWorkDraft) -> None:
        """Сохранить проверенную новую версию, не выполняя commit.

        Args:
            draft: Личная форма после проверки прав и версии.

        Raises:
            ValueError: Если у сохраняемой формы нет времени или срока хранения.
        """
        row = self.session.get(CaseWorkDraftRow, (draft.case_id, draft.user_id, draft.kind))
        if row is None:
            row = CaseWorkDraftRow(case_id=draft.case_id, user_id=draft.user_id, kind=draft.kind)
            self.session.add(row)
        content = draft.content
        row.version = draft.version
        row.content = {
            'text': content.text,
            'findings': content.findings,
            'next_actions': content.next_actions,
            'record_ids': [str(item) for item in content.record_ids],
            **{
                key: str(value) if value else None
                for key, value in {
                    'parent_id': content.parent_id,
                    'opinion_id': content.opinion_id,
                    'assignee_id': content.assignee_id,
                    'attachment_id': content.attachment_id,
                    'idempotency_key': content.idempotency_key,
                }.items()
            },
        }
        if draft.updated_at is None or draft.expires_at is None:
            raise ValueError('Для сохраняемой формы требуется срок хранения')
        row.updated_at, row.expires_at = draft.updated_at, draft.expires_at
        self.session.flush()

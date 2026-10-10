"""Сохранение личного текста с полной проверкой клинического контекста."""

from datetime import datetime, timedelta, UTC
from uuid import UUID

from app.application.ports.case_drafts import CaseDraftRepositoryPort
from app.application.use_cases.clinical_cases.context import CaseContext
from app.domain.case_drafts import CaseDraftContent, CaseWorkDraft, DraftKind
from app.domain.clinical_cases import CaseError


class CaseWorkDraftsUseCase:
    """Личные черновики, доступные семь дней и не создающие общую активность."""

    def __init__(self, context: CaseContext, drafts: CaseDraftRepositoryPort) -> None:
        """Связать проверку случая с личным хранилищем текущей транзакции.

        Args:
            context: Политика доступа и проверка ссылок случая.
            drafts: Хранилище личных незавершённых форм.
        """
        self.context = context
        self.drafts = drafts

    def get(self, case_id: UUID, user_id: UUID, kind: DraftKind) -> CaseWorkDraft:
        """Восстановить форму только при текущем полном доступе к случаю.

        Args:
            case_id: Клинический случай.
            user_id: Автор восстанавливаемой формы.
            kind: Сообщение, запрос мнения или итог.

        Returns:
            Сохранённая форма либо пустая форма с нулевой версией.
        """
        case = self.context.load(case_id, user_id, lock=True)
        self.context.require_context(case, user_id)
        if kind == 'conclusion':
            case.require_coordinator(user_id)
        return self.drafts.get(case_id, user_id, kind, datetime.now(UTC)) or CaseWorkDraft(case_id, user_id, kind)

    def save(
        self, case_id: UUID, user_id: UUID, kind: DraftKind, version: int, content: CaseDraftContent
    ) -> CaseWorkDraft:
        """Сохранить форму, не перезаписывая работу в другой вкладке.

        Args:
            case_id: Клинический случай.
            user_id: Автор формы из аутентификации.
            kind: Вид формы.
            version: Последняя прочитанная версия личного черновика.
            content: Незавершённый текст и ссылки на материалы.

        Returns:
            Следующая версия с временем сохранения и сроком хранения.

        Raises:
            CaseError: При устаревшей версии, закрытом случае или недействительных ссылках.
        """
        case = self.context.load(case_id, user_id, lock=True)
        self.context.require_context(case, user_id)
        case.require_writable()
        if kind == 'conclusion':
            case.require_coordinator(user_id)
        if any(len(text) > 10000 for text in (content.text, content.findings, content.next_actions)):
            raise CaseError('Текст черновика превышает допустимую длину', 422)
        if len(content.record_ids) > 100 or (kind != 'conclusion' and len(content.record_ids) > 1):
            raise CaseError('Недопустимое число ссылок', 422)
        for record_id in content.record_ids:
            self.context.reference(case, user_id, record_id)
        self.context.reference(case, user_id, next(iter(content.record_ids), None), content.attachment_id)
        if content.parent_id:
            parent = self.context.repository.message(content.parent_id)
            if parent is None or parent.case_id != case_id or parent.parent_id:
                raise CaseError('Исходное сообщение недоступно', 422)
        if content.opinion_id:
            opinion = self.context.repository.opinion(content.opinion_id)
            if opinion is None or opinion.case_id != case_id or opinion.assignee_id != user_id:
                raise CaseError('Запрос мнения недоступен', 403)
        if content.assignee_id:
            member = case.member(content.assignee_id)
            if (
                content.assignee_id == user_id
                or not self.context.repository.is_doctor(content.assignee_id)
                or (content.assignee_id != case.coordinator_id and (member is None or member.status != 'accepted'))
            ):
                raise CaseError('Адресат больше не участвует в случае', 422)
        now = datetime.now(UTC)
        current = self.drafts.get(case_id, user_id, kind, now)
        if version != (current.version if current else 0):
            raise CaseError('Черновик изменён в другой вкладке. Перечитайте его перед продолжением', 409)
        draft = CaseWorkDraft(case_id, user_id, kind, version + 1, content, now, now + timedelta(days=7))
        self.drafts.save(draft)
        return draft

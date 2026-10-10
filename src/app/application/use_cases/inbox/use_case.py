"""Пагинация действующих задач после повторной проверки контекста."""

from dataclasses import asdict
from uuid import UUID

from app.application.ports.inbox import InboxRepositoryPort
from app.application.ports.notifications import NotificationRepositoryPort
from app.application.use_cases.clinical_cases.context import CaseContext
from app.application.use_cases.clinical_cases.dtos import PageDTO
from app.application.use_cases.inbox.dtos import InboxCounts, InboxTask, TaskKind
from app.domain.clinical_cases import CaseError


class InboxUseCase:
    """Соединить существующие состояния задач и одинаковую политику доступа."""

    def __init__(
        self, repository: InboxRepositoryPort, notifications: NotificationRepositoryPort, cases: CaseContext
    ) -> None:
        """Инициализировать порты текущей транзакции.

        Args:
            repository: Кандидаты задач в серверном порядке.
            notifications: Существующие счётчики событий.
            cases: Политика доступа к случаям.
        """
        self.repository, self.notifications, self.cases = repository, notifications, cases

    def tasks(self, user_id: UUID, kind: TaskKind | None, offset: int, limit: int) -> PageDTO[InboxTask]:
        """Проверить доступ до итоговой пагинации и подсчёта.

        Args:
            user_id: Активный врач.
            kind: Тип задачи или все типы.
            offset: Смещение разрешённых задач.
            limit: Размер итоговой страницы.

        Returns:
            Страница действующих доступных задач с точным общим числом.
        """
        self.cases.require_doctor(user_id)
        items: list[InboxTask] = []
        total, cursor = 0, 0
        while batch := self.repository.candidates(user_id, kind, cursor, 100):
            cursor += len(batch)
            for task in batch:
                context = None
                if task.case_id:
                    try:
                        case = self.cases.load(task.case_id, user_id)
                        if case.status != 'active':
                            continue
                        if task.kind == 'invitation':
                            member = case.member(user_id)
                            if (
                                not member
                                or member.status != 'pending'
                                or not self.cases.repository.is_doctor(case.coordinator_id)
                            ):
                                continue
                            context = f'{len(case.record_ids)} материалов'
                        else:
                            self.cases.require_context(case, user_id)
                            context = case.title
                    except CaseError:
                        continue
                if offset <= total < offset + limit:
                    items.append(InboxTask(**asdict(task), key=f'{task.kind}:{task.id}', context=context))
                total += 1
        return PageDTO(items, total)

    def counts(self, user_id: UUID) -> InboxCounts:
        """Получить отдельные счётчики без смешивания задач и прочтения.

        Args:
            user_id: Активный врач.

        Returns:
            Количество задач по типам и непрочитанных событий.
        """
        kinds: tuple[TaskKind, ...] = ('invitation', 'opinion_requested', 'share_request', 'import_review')
        counts = {kind: self.tasks(user_id, kind, 0, 0).total for kind in kinds}
        _, unread, _ = self.notifications.counts(user_id)
        return InboxCounts(sum(counts.values()), counts, unread)

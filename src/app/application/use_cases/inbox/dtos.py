"""Типизированные проекции входящих без отдельного хранения медицинского текста."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

TaskKind = Literal['invitation', 'opinion_requested', 'share_request', 'import_review']


@dataclass(frozen=True)
class TaskCandidate:
    """Ссылки на текущее состояние сущностей до повторной проверки доступа."""

    kind: TaskKind
    id: UUID
    case_id: UUID | None
    actor_name: str | None
    created_at: datetime
    description: str | None


@dataclass(frozen=True)
class InboxTask(TaskCandidate):
    """Разрешённая задача с типизированной целью перехода."""

    key: str
    context: str | None


@dataclass(frozen=True)
class InboxCounts:
    """Задачи и непрочитанные события имеют разный смысл и разные счётчики."""

    tasks: int
    by_type: dict[TaskKind, int]
    unread_events: int

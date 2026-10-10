"""Личные незавершённые тексты клинического разбора."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

DraftKind = Literal['message', 'opinion', 'conclusion']


@dataclass(frozen=True)
class CaseDraftContent:
    """Текст и выбранные ссылки; черновик не становится сообщением или итогом."""

    text: str = ''
    findings: str = ''
    next_actions: str = ''
    record_ids: tuple[UUID, ...] = ()
    parent_id: UUID | None = None
    opinion_id: UUID | None = None
    assignee_id: UUID | None = None
    attachment_id: UUID | None = None
    idempotency_key: UUID | None = None


@dataclass(frozen=True)
class CaseWorkDraft:
    """Версия личной формы для безопасного восстановления и конкурентных вкладок."""

    case_id: UUID
    user_id: UUID
    kind: DraftKind
    version: int = 0
    content: CaseDraftContent = field(default_factory=CaseDraftContent)
    updated_at: datetime | None = None
    expires_at: datetime | None = None

"""Порт хранения личных форм без зависимости от ORM и JSON."""

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.case_drafts import CaseWorkDraft, DraftKind


class CaseDraftRepositoryPort(Protocol):
    """Хранение под блокировкой случая, взятой прикладным сценарием."""

    def get(self, case_id: UUID, user_id: UUID, kind: DraftKind, now: datetime) -> CaseWorkDraft | None:
        """Прочитать личный черновик и удалить его при истечении срока.

        Args:
            case_id: Случай, контекст которого уже проверен.
            user_id: Автор формы, определённый из аутентификации.
            kind: Вид незавершённой формы.
            now: Текущее время для проверки срока хранения.

        Returns:
            Неистёкший черновик либо None.
        """
        ...

    def save(self, draft: CaseWorkDraft) -> None:
        """Сохранить следующую версию в текущей транзакции.

        Args:
            draft: Новая версия личной формы после проверок доступа и версии.
        """
        ...

"""Порт объединённой серверной выборки актуальных задач."""

from typing import Protocol
from uuid import UUID

from app.application.use_cases.inbox.dtos import TaskCandidate, TaskKind


class InboxRepositoryPort(Protocol):
    """Получение ограниченных порций кандидатов в порядке очереди."""

    def candidates(self, user_id: UUID, kind: TaskKind | None, offset: int, limit: int) -> list[TaskCandidate]:
        """Выбрать задачи адресата без копирования клинического содержимого.

        Args:
            user_id: Адресат или владелец импорта.
            kind: Фильтр типа; None выбирает все типы.
            offset: Смещение в выборке кандидатов.
            limit: Размер порции.

        Returns:
            Новые кандидаты сначала, с устойчивым вторичным порядком.
        """
        ...

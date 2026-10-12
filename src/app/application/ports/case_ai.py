"""Порты личной AI-сводки и извлечения подтверждённых источниками фактов."""

from typing import Protocol
from uuid import UUID

from app.application.ports.import_jobs.ai import DocumentPage
from app.domain.case_ai import CaseSummaryRun, SummaryDocument, SummaryExtraction
from app.domain.import_ai import AiOptions


class CaseSummaryProviderPort(Protocol):
    """Извлечение фактов выбранного документа без действий в Docere."""

    def extract(self, pages: tuple[DocumentPage, ...]) -> tuple[SummaryExtraction, dict[str, int]]:
        """Вернуть факты со ссылками только на переданные страницы."""
        ...


class CaseSummaryRepositoryPort(Protocol):
    """Хранилище запусков в текущей транзакции случая."""

    def find(self, case_id: UUID, user_id: UUID, key: UUID) -> CaseSummaryRun | None:
        """Найти повтор запуска без внешнего вызова."""
        ...

    def get(self, case_id: UUID, user_id: UUID, run_id: UUID | None) -> CaseSummaryRun | None:
        """Получить собственный запуск или последний; чужие результаты скрыты."""
        ...

    def selection(self, run_id: UUID) -> tuple[UUID, ...]:
        """Прочитать исходный выбор для проверки идемпотентного повтора."""
        ...

    def sources_current(self, run_id: UUID) -> bool:
        """Проверить, что записи не изменились со времени создания снимка."""
        ...

    def active(self, case_id: UUID, user_id: UUID) -> bool:
        """Не создавать два действующих запуска одного врача в одном случае."""
        ...

    def create(
        self,
        case_id: UUID,
        user_id: UUID,
        key: UUID,
        record_ids: tuple[UUID, ...],
        documents: tuple[SummaryDocument, ...],
        options: AiOptions,
    ) -> CaseSummaryRun:
        """Атомарно сохранить снимок выбора и намерение доставки."""
        ...

    def cancel(self, run_id: UUID) -> CaseSummaryRun:
        """Отменить незавершённые документы с fencing поздних ответов."""
        ...

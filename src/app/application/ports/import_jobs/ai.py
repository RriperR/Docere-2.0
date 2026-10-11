"""Порты подготовки страниц, AI-провайдера и персистентных запусков."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.import_ai import AiExtraction, AiOptions, AiRun, AiStartContext


@dataclass(frozen=True, slots=True)
class DocumentPage:
    """Страница для внешнего анализа."""

    number: int
    text: str
    image_base64: str


class DocumentPagesPort(Protocol):
    """Локальное чтение и рендеринг безопасно загруженного документа."""

    def prepare(self, content: bytes, mime_type: str, max_pages: int) -> tuple[DocumentPage, ...]:
        """Вернуть все страницы либо ошибку без частичного результата."""
        ...


class ImportAiProviderPort(Protocol):
    """Провайдер извлекает факты, не выполняя действий в Docere."""

    def extract(self, pages: tuple[DocumentPage, ...]) -> tuple[AiExtraction, dict[str, int]]:
        """Вернуть проверенные факты и доступную статистику использования."""
        ...


class ImportAiRepositoryPort(Protocol):
    """Персистентные запуски с транзакционной доставкой и защитой доступа."""

    def start_context(self, job_id: UUID, user_id: UUID, role: str, key: UUID) -> AiStartContext:
        """Захватить импорт и вернуть актуальное состояние для решения use case."""
        ...

    def create(self, job_id: UUID, user_id: UUID, file_ids: tuple[str, ...], key: UUID, options: AiOptions) -> AiRun:
        """Сохранить запуск в той же транзакции, что и start_context."""
        ...

    def get(self, job_id: UUID, run_id: UUID, user_id: UUID, role: str) -> AiRun:
        """Получить запуск после повторной проверки доступа."""
        ...

    def cancel(self, job_id: UUID, run_id: UUID, user_id: UUID, role: str) -> AiRun:
        """Отменить оставшуюся обработку и отбросить поздние результаты."""
        ...

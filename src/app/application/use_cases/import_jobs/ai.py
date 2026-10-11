"""Сценарии запуска AI и анализа выбранного документа."""

from collections.abc import Callable
from hashlib import sha256
from uuid import UUID

from app.application.ports.import_jobs.ai import DocumentPagesPort, ImportAiProviderPort, ImportAiRepositoryPort
from app.domain.import_ai import AiExtraction, AiOptions, AiRun, ImportAiError, merge_extractions


class ImportAiUseCase:
    """Управлять предложениями, сохраняя ручную проверку отдельным действием."""

    def __init__(self, repository: ImportAiRepositoryPort, options: AiOptions) -> None:
        """Связать персистентные запуски и ограничения сервера."""
        self.repository, self.options = repository, options

    def start(
        self, job_id: UUID, user_id: UUID, role: str, file_ids: tuple[str, ...], key: UUID, version: int
    ) -> AiRun:
        """Проверить выбор и создать транзакционное намерение анализа.

        Returns:
            Запуск для опроса статуса.

        Raises:
            ImportAiError: AI выключен или число выбранных документов недопустимо.
        """
        if not self.options.enabled:
            raise ImportAiError('ai_unavailable', 503)
        if not file_ids or len(file_ids) > self.options.max_documents or len(set(file_ids)) != len(file_ids):
            raise ImportAiError('document_limit')
        context = self.repository.start_context(job_id, user_id, role, key)
        if context.owner_id != str(user_id):
            raise ImportAiError('owner_required', 403)
        if context.repeated_run is not None:
            if set(file_ids) != {d.file_id for d in context.repeated_run.documents}:
                raise ImportAiError('idempotency_conflict', 409)
            return context.repeated_run
        if context.status != 'needs_review' or context.version != version:
            raise ImportAiError('review_conflict', 409)
        if context.active:
            raise ImportAiError('analysis_running', 409)
        files = {f.id: f for f in context.files}
        if any(
            fid not in files
            or files[fid].is_dicom
            or files[fid].mime_type not in {'application/pdf', 'image/png', 'image/jpeg'}
            for fid in file_ids
        ):
            raise ImportAiError('unsupported_document')
        return self.repository.create(job_id, user_id, file_ids, key, self.options)


class AnalyzeImportDocumentUseCase:
    """Подготовить страницы и собрать факты без публикации в историю."""

    def __init__(self, pages: DocumentPagesPort, provider: ImportAiProviderPort, options: AiOptions) -> None:
        """Связать локальную подготовку с внешним извлечением фактов."""
        self.pages, self.provider, self.options = pages, provider, options

    def analyze(
        self, content: bytes, mime_type: str, remaining_pages: int, authorized: 'AuthorizationCheck'
    ) -> tuple[dict[str, object], int, str, dict[str, int]]:
        """Проанализировать весь документ, повторно проверяя доступ перед каждым вызовом.

        Args:
            content: Содержимое выбранного документа.
            mime_type: Проверенный MIME-тип.
            remaining_pages: Остаток общего бюджета страниц.
            authorized: Повторная проверка актуального пользователя и запуска.

        Returns:
            Предложения, число страниц, SHA-256 и статистика токенов.

        Raises:
            ImportAiError: Лимит страниц или потеря доступа.
        """
        pages = self.pages.prepare(content, mime_type, self.options.max_pages_per_document)
        if len(pages) > remaining_pages:
            raise ImportAiError('page_limit')
        batches: list[AiExtraction] = []
        usage: dict[str, int] = {}
        try:
            for offset in range(0, len(pages), self.options.batch_pages):
                if not authorized():
                    raise ImportAiError('cancelled', 409)
                batch, stats = self.provider.extract(pages[offset : offset + self.options.batch_pages])
                batches.append(batch)
                for name, value in stats.items():
                    usage[name] = usage.get(name, 0) + value
        except ImportAiError as exc:
            exc.page_count, exc.checksum, exc.usage = len(pages), sha256(content).hexdigest(), usage
            raise
        return merge_extractions(batches), len(pages), sha256(content).hexdigest(), usage


AuthorizationCheck = Callable[[], bool]

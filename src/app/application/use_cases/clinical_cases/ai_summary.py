"""Выбор материалов и анализ документов для личной фактической сводки врача."""

from collections.abc import Callable
from dataclasses import replace
from hashlib import sha256
from uuid import UUID

from app.application.ports.case_ai import CaseSummaryProviderPort, CaseSummaryRepositoryPort
from app.application.ports.import_jobs.ai import DocumentPagesPort
from app.application.use_cases.clinical_cases.context import CaseContext
from app.domain.case_ai import (
    CaseSummaryRun,
    merge_summary_batches,
    SUMMARY_MIME_TYPES,
    SummaryDocument,
)
from app.domain.clinical_cases import CaseError
from app.domain.import_ai import AiOptions, ImportAiError


class CaseSummaryUseCase:
    """Запуск сводки после явного согласия и проверки всего контекста случая."""

    def __init__(self, context: CaseContext, repository: CaseSummaryRepositoryPort, options: AiOptions) -> None:
        """Связать общую политику доступа, хранилище и серверные лимиты."""
        self.context, self.repository, self.options = context, repository, options

    def start(
        self,
        case_id: UUID,
        user_id: UUID,
        record_ids: tuple[UUID, ...],
        key: UUID,
        version: int,
        consent: bool,
    ) -> CaseSummaryRun:
        """Сохранить намерение анализа только выбранных материалов.

        Args:
            case_id: Случай, доступ ко всем материалам которого обязателен.
            user_id: Врач, владелец личной сводки.
            record_ids: Явно выбранные записи без дубликатов.
            key: Ключ идемпотентности HTTP-запроса.
            version: Версия случая, показанная врачу при выборе.
            consent: Явное согласие отправить вложения внешнему провайдеру.

        Returns:
            Новый либо повторный запуск.

        Raises:
            CaseError: Доступ, выбор, согласие или версия недопустимы.
        """
        case = self.context.load(case_id, user_id, lock=True)
        self.context.require_context(case, user_id)
        if not consent:
            raise CaseError('Подтвердите передачу выбранных документов внешнему AI-сервису', 422)
        if not record_ids or len(record_ids) > self.options.max_documents or len(set(record_ids)) != len(record_ids):
            raise CaseError('Выберите допустимое число записей без повторов', 422)
        for record_id in record_ids:
            self.context.reference(case, user_id, record_id)
        repeated = self.repository.find(case_id, user_id, key)
        if repeated:
            if set(record_ids) != set(self.repository.selection(repeated.id)):
                raise CaseError('Ключ запуска уже использован с другим выбором', 409)
            self._current(repeated)
            return repeated
        if not self.options.enabled:
            raise CaseError('AI-сервис не настроен. Материалы доступны для обычного просмотра', 503)
        if case.version != version:
            raise CaseError('Случай изменился. Обновите выбор материалов', 409)
        if self.repository.active(case_id, user_id):
            raise CaseError('Анализ этого случая уже выполняется', 409)
        documents: list[SummaryDocument] = []
        for record_id in record_ids:
            record = self.context.records.get_accessible_record(record_id, user_id)
            if record is None:
                raise CaseError('Материал недоступен', 403)
            files = [f for f in record.attachments if f.comment_id is None]
            for file in files:
                supported = file.mime_type in SUMMARY_MIME_TYPES
                documents.append(
                    SummaryDocument(
                        record_id,
                        file.id,
                        record.record.title or 'Медицинская запись',
                        record.record.event_date,
                        file.filename or 'Документ',
                        file.mime_type,
                        status='queued' if supported else 'skipped',
                        error_code=None if supported else 'unsupported_document',
                    )
                )
            if not files:
                documents.append(
                    SummaryDocument(
                        record_id,
                        None,
                        record.record.title or 'Медицинская запись',
                        record.record.event_date,
                        '',
                        '',
                        status='skipped',
                        error_code='no_documents',
                    )
                )
        supported_count = sum(d.status == 'queued' for d in documents)
        if not supported_count or supported_count > self.options.max_documents or len(documents) > 100:
            raise CaseError('Выберите записи с PDF/PNG/JPEG в пределах лимита документов', 422)
        return self.repository.create(case_id, user_id, key, record_ids, tuple(documents), self.options)

    def get(self, case_id: UUID, user_id: UUID, run_id: UUID | None = None) -> CaseSummaryRun | None:
        """Перечитать результат только после проверки членства и всех материалов.

        Returns:
            Собственный результат либо None, если запусков ещё нет.

        Raises:
            CaseError: Контекст недоступен или источники изменились.
        """
        case = self.context.load(case_id, user_id)
        self.context.require_context(case, user_id)
        run = self.repository.get(case_id, user_id, run_id)
        if run_id and run is None:
            raise CaseError('Сводка не найдена', 404)
        if run:
            for record_id in self.repository.selection(run.id):
                self.context.reference(case, user_id, record_id)
            self._current(run)
        return run

    def cancel(self, case_id: UUID, user_id: UUID, run_id: UUID) -> CaseSummaryRun:
        """Отменить собственный запуск независимо от актуальности снимка.

        Returns:
            Состояние после отмены.

        Raises:
            CaseError: Доступ или принадлежность запуска недопустимы.
        """
        self.context.require_context(self.context.load(case_id, user_id, lock=True), user_id)
        run = self.repository.get(case_id, user_id, run_id)
        if run is None:
            raise CaseError('Сводка не найдена', 404)
        return self.repository.cancel(run.id)

    def _current(self, run: CaseSummaryRun) -> None:
        if not self.repository.sources_current(run.id):
            raise CaseError('Материалы изменились. Подготовьте новую сводку', 409)


class AnalyzeCaseDocumentUseCase:
    """Анализ полного документа с проверками между пакетами страниц."""

    def __init__(self, pages: DocumentPagesPort, provider: CaseSummaryProviderPort, options: AiOptions) -> None:
        """Связать подготовку страниц, модель и лимиты одного запуска."""
        self.pages, self.provider, self.options = pages, provider, options

    def analyze(
        self,
        document: SummaryDocument,
        content: bytes,
        remaining_pages: int,
        authorized: Callable[[], bool],
    ) -> SummaryDocument:
        """Извлечь факты, сохранив происхождение и целостность документа.

        Returns:
            Завершённый документ с SHA-256 и источниками каждого факта.

        Raises:
            ImportAiError: Нечитаемый документ, лимит, отмена или ошибка провайдера.
        """
        pages = self.pages.prepare(content, document.mime_type, self.options.max_pages_per_document)
        if len(pages) > remaining_pages:
            raise ImportAiError('page_limit')
        batches = []
        usage: dict[str, int] = {}
        try:
            for offset in range(0, len(pages), self.options.batch_pages):
                if not authorized():
                    raise ImportAiError('cancelled', 409)
                batch, stats = self.provider.extract(pages[offset : offset + self.options.batch_pages])
                batches.append(batch)
                for name, count in stats.items():
                    usage[name] = usage.get(name, 0) + count
            result = merge_summary_batches(batches)
            if result.multiple_patients:
                raise ImportAiError('multiple_patients_document')
        except ImportAiError as exc:
            exc.page_count, exc.checksum, exc.usage = len(pages), sha256(content).hexdigest(), usage
            raise
        issues = result.issues
        if result.event_date and result.event_date != document.record_date:
            issues += ('Дата в документе отличается от даты записи. Сверьте оригинал.',)
        return replace(
            document,
            status='completed',
            facts=result.facts,
            issues=issues,
            document_date=result.event_date,
            page_count=len(pages),
            checksum=sha256(content).hexdigest(),
            usage=usage,
        )

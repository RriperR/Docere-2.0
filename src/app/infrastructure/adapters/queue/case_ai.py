"""Персистентная доставка сводок с проверкой ACL, lease и fencing результатов."""

from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta, UTC
from typing import cast
from uuid import UUID, uuid4

import structlog
from pydantic import TypeAdapter
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.application.use_cases.clinical_cases.ai_summary import AnalyzeCaseDocumentUseCase
from app.application.use_cases.clinical_cases.context import CaseContext
from app.domain.case_ai import SUMMARY_ACTIVE, SUMMARY_PROMPT_VERSION, SummaryDocument
from app.domain.clinical_cases import CaseError
from app.domain.import_ai import AiOptions, ImportAiError
from app.infrastructure.adapters.case_ai.provider import ChatCompletionsCaseSummaryProvider
from app.infrastructure.adapters.import_jobs.ai_provider import ChatCompletionsImportProvider
from app.infrastructure.adapters.import_jobs.document_pages import DocumentPages
from app.infrastructure.adapters.queue.celery_app import celery_app
from app.infrastructure.adapters.queue.import_ai import DispatchedTask, LEASE_SECONDS
from app.infrastructure.adapters.repositories.case_ai import (
    serialize_documents,
    SqlAlchemyCaseSummaryRepository,
    summary_to_domain,
)
from app.infrastructure.adapters.repositories.clinical_cases import SqlAlchemyCaseRepository
from app.infrastructure.adapters.repositories.medical_records.sqlalchemy_medical_record_repository import (
    SqlAlchemyMedicalRecordRepositoryAdapter,
)
from app.infrastructure.adapters.storage.factory import get_file_storage
from app.infrastructure.config.settings import get_settings
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.case_ai import CaseSummaryRunRow
from app.infrastructure.db.models.clinical_cases import ClinicalCaseRow
from app.infrastructure.db.models.import_ai import ImportAiRunRow
from app.infrastructure.db.session import get_session_factory

logger = structlog.get_logger(__name__)
_options_adapter = TypeAdapter(AiOptions)


def _locked(session: Session, run_id: UUID) -> CaseSummaryRunRow | None:
    row = session.get(CaseSummaryRunRow, run_id)
    if row is None:
        return None
    # Один порядок case -> run у HTTP-сценариев, worker и dispatcher.
    session.scalar(select(ClinicalCaseRow).where(ClinicalCaseRow.id == row.case_id).with_for_update())
    return session.scalar(
        select(CaseSummaryRunRow)
        .where(CaseSummaryRunRow.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _valid(session: Session, row: CaseSummaryRunRow) -> bool:
    context = CaseContext(SqlAlchemyCaseRepository(session), SqlAlchemyMedicalRecordRepositoryAdapter(session))
    try:
        case = context.load(row.case_id, row.user_id)
        context.require_context(case, row.user_id)
        repo = SqlAlchemyCaseSummaryRepository(session)
        if not repo.sources_current(row.id):
            return False
        for record_id in repo.selection(row.id):
            context.reference(case, row.user_id, record_id)
        return True
    except CaseError:
        return False


def claim_summary(run_id: UUID, token: UUID) -> tuple[CaseSummaryRunRow, AiOptions] | None:
    """Захватить запуск с общим лимитом внешних запросов импорта и сводок.

    Returns:
        Независимый снимок строки и настроек либо None при повторе/занятом слоте.
    """
    with get_session_factory()() as session:
        if session.get_bind().dialect.name == 'postgresql':
            session.execute(text('SELECT pg_advisory_xact_lock(61831011)'))
        row = _locked(session, run_id)
        if row is None or row.status != 'queued':
            return None
        if not _valid(session, row):
            SqlAlchemyCaseSummaryRepository(session).cancel(run_id)
            session.commit()
            return None
        running = sum(
            session.scalar(select(func.count()).select_from(model).where(model.status == 'running')) or 0
            for model in (ImportAiRunRow, CaseSummaryRunRow)
        )
        if running >= get_settings().import_ai.concurrency:
            return None
        row.status, row.processing_token = 'running', token
        row.lease_expires_at = utc_now() + timedelta(seconds=LEASE_SECONDS)
        options = _options_adapter.validate_python(row.options_json)
        session.commit()
        session.refresh(row)
        session.expunge(row)
        return row, options


def summary_authorized(run_id: UUID, token: UUID) -> bool:
    """Повторно проверить весь ACL и актуальность снимка перед каждым внешним запросом.

    Returns:
        Право текущего worker продолжать обработку.
    """
    with get_session_factory()() as session:
        row = _locked(session, run_id)
        if row is None or row.status != 'running' or row.processing_token != token:
            return False
        if not _valid(session, row):
            SqlAlchemyCaseSummaryRepository(session).cancel(run_id)
            session.commit()
            return False
        row.lease_expires_at = utc_now() + timedelta(seconds=LEASE_SECONDS)
        session.commit()
        return True


def save_summary_document(run_id: UUID, token: UUID, result: SummaryDocument) -> bool:
    """Сохранить результат файла только при действующем ACL и lease-token.

    Returns:
        False для позднего ответа, отзыва доступа или завершённого документа.
    """
    with get_session_factory()() as session:
        row = _locked(session, run_id)
        if row is None or row.status != 'running' or row.processing_token != token:
            return False
        if not _valid(session, row):
            SqlAlchemyCaseSummaryRepository(session).cancel(run_id)
            session.commit()
            return False
        documents = summary_to_domain(row).documents
        current = next(
            (d for d in documents if d.attachment_id == result.attachment_id and d.record_id == result.record_id), None
        )
        if current is None or current.status != 'queued':
            return False
        row.documents_json = serialize_documents(tuple(result if d == current else d for d in documents))
        session.commit()
        return True


def finish_summary(run_id: UUID, token: UUID) -> None:
    """Завершить запуск, сохранив частичный успех и отменив остаток при потере доступа."""
    with get_session_factory()() as session:
        row = _locked(session, run_id)
        if row is None or row.status != 'running' or row.processing_token != token:
            return
        documents = summary_to_domain(row).documents
        if not _valid(session, row) or any(d.status == 'queued' for d in documents):
            SqlAlchemyCaseSummaryRepository(session).cancel(run_id)
        else:
            completed = sum(d.status == 'completed' for d in documents)
            errors = any(d.status != 'completed' for d in documents)
            row.status = 'completed_with_errors' if completed and errors else 'completed' if completed else 'failed'
            row.processing_token, row.finished_at = None, utc_now()
        session.commit()


SummaryTask = Callable[..., None]
summary_decorator = cast(
    Callable[[SummaryTask], SummaryTask],
    celery_app.task(
        name='docere.case_summary',
        soft_time_limit=1740,
        time_limit=1800,
        acks_late=True,
        reject_on_worker_lost=True,
    ),
)


@summary_decorator
def process_case_summary(run_id: str) -> None:
    """Проанализировать выбранные вложения; внешние вызовы выполняются вне транзакций.

    Args:
        run_id: Идентификатор намерения без медицинского содержимого.

    Raises:
        SQLAlchemyError: Сбой БД сохраняет lease для повторной доставки.
        ImportAiError: Ошибка документа перехватывается и сохраняется как отдельный результат.
    """
    rid, token = UUID(run_id), uuid4()
    claimed = claim_summary(rid, token)
    if claimed is None:
        return
    row, options = claimed
    cfg = get_settings().import_ai

    def check() -> bool:
        return summary_authorized(rid, token)

    provider = ChatCompletionsCaseSummaryProvider(
        ChatCompletionsImportProvider(
            cfg.base_url,
            row.model,
            cfg.token.get_secret_value(),
            cfg.timeout_seconds,
            authorized=check,
            disable_thinking=cfg.disable_thinking,
        )
    )
    analyze = AnalyzeCaseDocumentUseCase(DocumentPages(), provider, options)
    documents = summary_to_domain(row).documents
    remaining = options.max_pages - sum(d.page_count for d in documents if d.status != 'queued')
    for document in documents:
        if document.status != 'queued':
            continue
        if not check():
            break
        try:
            if (
                not cfg.options().enabled
                or cfg.model != row.model
                or cfg.provider != row.provider
                or row.prompt_version != SUMMARY_PROMPT_VERSION
            ):
                raise ImportAiError('configuration_changed', 503)
            with get_session_factory()() as session:
                if document.attachment_id is None:
                    raise ImportAiError('source_changed')
                attachment = SqlAlchemyMedicalRecordRepositoryAdapter(session).get_attachment(
                    attachment_id=document.attachment_id,
                )
                if attachment is None or attachment.record_id != document.record_id:
                    raise ImportAiError('source_changed')
                if attachment.size_bytes > 30 * 1024 * 1024:
                    raise ImportAiError('document_size_limit')
                key = attachment.storage_key
            content = get_file_storage().download(key=key)
            if len(content) > 30 * 1024 * 1024:
                raise ImportAiError('document_size_limit')
            result = analyze.analyze(document, content, remaining, check)
        except ImportAiError as exc:
            if exc.code == 'cancelled':
                break
            result = replace(
                document,
                status='failed',
                error_code=exc.code,
                page_count=exc.page_count,
                checksum=exc.checksum,
                usage=exc.usage,
            )
        except SQLAlchemyError:
            raise
        except Exception:
            result = replace(document, status='failed', error_code='processing_error')
            logger.warning('case_summary_document_error', run_id=run_id)
        if not save_summary_document(rid, token, result):
            break
        remaining -= result.page_count
    finish_summary(rid, token)


def enqueue_case_summaries(limit: int = 100) -> int:
    """Восстановить lease и повторить доставку, сохраняя запуск при недоступности Redis.

    Returns:
        Число сообщений, принятых брокером; дубликаты безопасны благодаря claim и fencing.

    Raises:
        SQLAlchemyError: Недоступность БД; намерение будет доставлено следующим проходом.
    """
    with get_session_factory()() as session:
        session.execute(
            update(CaseSummaryRunRow)
            .where(
                CaseSummaryRunRow.status == 'running',
                CaseSummaryRunRow.lease_expires_at <= utc_now(),
            )
            .values(status='queued', processing_token=None, next_delivery_at=utc_now())
        )
        session.commit()
    # Заблокировать отдельную строку случая до проверки, чтобы отзыв и новая доставка не гонялись.
    with get_session_factory()() as session:
        ids = session.scalars(
            select(CaseSummaryRunRow.id)
            .where(CaseSummaryRunRow.status.in_(SUMMARY_ACTIVE))
            .order_by(CaseSummaryRunRow.created_at)
            .limit(limit)
        ).all()
    delivered = 0
    for run_id in ids:
        with get_session_factory()() as session:
            row = _locked(session, run_id)
            if row is None or row.status not in SUMMARY_ACTIVE:
                continue
            if not _valid(session, row):
                SqlAlchemyCaseSummaryRepository(session).cancel(run_id)
            elif row.status == 'queued' and row.next_delivery_at.replace(tzinfo=UTC) <= utc_now():
                try:
                    cast(DispatchedTask, process_case_summary).apply_async(args=[str(row.id)])
                    delivered += 1
                except SQLAlchemyError:
                    raise
                except Exception:
                    logger.warning('case_summary_dispatch_retry', run_id=str(row.id))
                row.delivery_attempts += 1
                row.next_delivery_at = utc_now() + timedelta(seconds=60)
            session.commit()
    return delivered

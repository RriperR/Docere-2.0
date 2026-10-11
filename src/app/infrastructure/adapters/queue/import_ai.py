"""Надёжная доставка AI-заданий, короткие транзакции и fencing результатов."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import cast, Protocol
from uuid import UUID, uuid4

import structlog
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.application.use_cases.import_jobs.ai import AnalyzeImportDocumentUseCase, ImportAiUseCase
from app.application.use_cases.import_jobs.documents import import_file_id, ReadImportSourceUseCase
from app.application.use_cases.import_jobs.use_cases import _as_dict_list
from app.domain.import_ai import AI_ACTIVE, AiOptions, AiRun, ImportAiError
from app.infrastructure.adapters.import_jobs.ai_provider import ChatCompletionsImportProvider
from app.infrastructure.adapters.import_jobs.document_pages import DocumentPages
from app.infrastructure.adapters.import_jobs.factory import build_zip_archive_reader
from app.infrastructure.adapters.queue.celery_app import celery_app
from app.infrastructure.adapters.repositories.import_ai import require_job, run_to_domain, SqlAlchemyImportAiRepository
from app.infrastructure.adapters.repositories.import_jobs.sqlalchemy_import_job_repository import (
    SqlAlchemyImportJobRepositoryAdapter,
)
from app.infrastructure.adapters.storage.factory import get_file_storage
from app.infrastructure.config.settings import get_settings
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.auth.user import UserRow
from app.infrastructure.db.models.import_ai import ImportAiDocumentRow, ImportAiRunRow
from app.infrastructure.db.models.medical_records.import_job import ImportJobRow
from app.infrastructure.db.session import get_session_factory

LEASE_SECONDS = 1920  # Больше hard limit Celery: погибший worker не продолжает занимать слот.
logger = structlog.get_logger(__name__)


def _options(row: ImportAiRunRow) -> AiOptions:
    raw = row.options_json
    return AiOptions(
        True,
        row.provider,
        row.model,
        int(str(raw.get('max_documents', 20))),
        int(str(raw.get('max_pages', 100))),
        int(str(raw.get('max_pages_per_document', 30))),
        int(str(raw.get('batch_pages', 5))),
        int(str(raw.get('concurrency', 2))),
    )


@dataclass(frozen=True)
class ClaimedAiRun:
    """Снимок запуска после фиксации lease, без открытой транзакции."""

    run: AiRun
    user_id: UUID
    role: str
    token: UUID
    options: AiOptions


def _locked_run(session: Session, run_id: UUID) -> ImportAiRunRow:
    run = session.get(ImportAiRunRow, run_id)
    if run is None:
        raise ImportAiError('not_found', 404)
    user = session.get(UserRow, run.user_id, populate_existing=True)
    require_job(session, run.job_id, run.user_id, user.role.value if user else '', lock=True)
    return session.scalars(
        select(ImportAiRunRow)
        .where(ImportAiRunRow.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()


def claim_ai_run(run_id: UUID, token: UUID) -> ClaimedAiRun | None:
    """Захватить queued-запуск с общим ограничением числа внешних запросов.

    Returns:
        Снимок запуска либо None для повтора или занятого слота.
    """
    with get_session_factory()() as session:
        if session.get_bind().dialect.name == 'postgresql':
            session.execute(text('SELECT pg_advisory_xact_lock(61831011)'))
        try:
            row = _locked_run(session, run_id)
        except ImportAiError:
            return None
        if row.status != 'queued':
            return None
        options = _options(row)
        running = session.scalar(
            select(func.count()).select_from(ImportAiRunRow).where(ImportAiRunRow.status == 'running')
        )
        if (running or 0) >= get_settings().import_ai.concurrency:
            return None
        user = session.get(UserRow, row.user_id)
        if user is None:
            return None
        job = require_job(session, row.job_id, row.user_id, user.role.value)
        if job.status.value != 'needs_review':
            row.status, row.finished_at = 'cancelled', utc_now()
            session.commit()
            return None
        row.status, row.processing_token = 'running', token
        row.lease_expires_at = utc_now() + timedelta(seconds=LEASE_SECONDS)
        snapshot = ClaimedAiRun(run_to_domain(session, row), row.user_id, user.role.value, token, options)
        session.commit()
        return snapshot


def ai_authorized(run_id: UUID, token: UUID) -> bool:
    """Повторно проверить доступ перед каждым вызовом и продлить lease.

    Returns:
        Право текущей попытки продолжать обработку.
    """
    with get_session_factory()() as session:
        try:
            row = _locked_run(session, run_id)
            user = session.get(UserRow, row.user_id)
            job = require_job(session, row.job_id, row.user_id, user.role.value if user else '')
            allowed = row.status == 'running' and row.processing_token == token and job.status.value == 'needs_review'
            if allowed:
                row.lease_expires_at = utc_now() + timedelta(seconds=LEASE_SECONDS)
            session.commit()
            return allowed
        except ImportAiError:
            return False


def save_ai_document(
    run_id: UUID,
    token: UUID,
    file_id: str,
    result: dict[str, object],
    page_count: int,
    checksum: str | None,
    usage: dict[str, int],
    error_code: str | None = None,
) -> bool:
    """Сохранить один результат при действующем доступе и token попытки.

    Returns:
        True, если результат принят.
    """
    with get_session_factory()() as session:
        try:
            row = _locked_run(session, run_id)
            user = session.get(UserRow, row.user_id)
            job = require_job(session, row.job_id, row.user_id, user.role.value if user else '')
        except ImportAiError:
            return False
        if row.status != 'running' or row.processing_token != token or job.status.value != 'needs_review':
            return False
        doc = session.get(ImportAiDocumentRow, (run_id, file_id))
        if doc is None or doc.status != 'queued':
            return False
        doc.status = 'failed' if error_code else 'completed'
        doc.result_json, doc.page_count, doc.checksum, doc.usage_json = result, page_count, checksum, usage
        doc.error_code, doc.finished_at = error_code, utc_now()
        session.commit()
        return True


def finish_ai_run(run_id: UUID, token: UUID) -> None:
    """Закончить попытку или отменить её при потере прав."""
    with get_session_factory()() as session:
        raw = session.get(ImportAiRunRow, run_id)
        if raw is None:
            return
        # Сначала тот же порядок job -> run, что у resolve/cancel.
        session.scalar(select(ImportJobRow).where(ImportJobRow.id == raw.job_id).with_for_update())
        row = session.scalars(
            select(ImportAiRunRow)
            .where(ImportAiRunRow.id == run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one()
        if row.status != 'running' or row.processing_token != token:
            return
        try:
            user = session.get(UserRow, row.user_id, populate_existing=True)
            job = require_job(session, row.job_id, row.user_id, user.role.value if user else '')
            valid = job.status.value == 'needs_review'
        except ImportAiError:
            valid = False
        docs = session.scalars(select(ImportAiDocumentRow).where(ImportAiDocumentRow.run_id == run_id)).all()
        completed = sum(d.status == 'completed' for d in docs)
        if not valid or any(d.status == 'queued' for d in docs):
            row.status = 'cancelled'
            for doc in docs:
                if doc.status == 'queued':
                    doc.status, doc.error_code = 'cancelled', 'cancelled'
        else:
            row.status = 'completed' if completed == len(docs) else 'completed_with_errors' if completed else 'failed'
        row.processing_token, row.finished_at = None, utc_now()
        session.commit()


AiTask = Callable[..., None]
ai_decorator = cast(
    Callable[[AiTask], AiTask],
    celery_app.task(
        name='docere.import_ai', soft_time_limit=1740, time_limit=1800, acks_late=True, reject_on_worker_lost=True
    ),
)


@ai_decorator
def process_import_ai(run_id: str) -> None:
    """Проанализировать выбранные файлы без длительной транзакции БД.

    Args:
        run_id: Идентификатор транзакционного намерения.

    Raises:
        SQLAlchemyError: Сбой БД оставляет lease для повторной доставки.
        ImportAiError: Конфигурация или доступ недопустимы; ошибка сохраняется по документу.
    """
    rid, token = UUID(run_id), uuid4()
    claimed = claim_ai_run(rid, token)
    if claimed is None:
        return
    cfg = get_settings().import_ai

    def check() -> bool:
        return ai_authorized(rid, token)

    provider = ChatCompletionsImportProvider(
        cfg.base_url,
        claimed.run.model,
        cfg.token.get_secret_value(),
        cfg.timeout_seconds,
        authorized=check,
        disable_thinking=cfg.disable_thinking,
    )
    analyze = AnalyzeImportDocumentUseCase(DocumentPages(), provider, claimed.options)
    remaining = claimed.options.max_pages - sum(d.page_count for d in claimed.run.documents if d.status != 'queued')
    for document in claimed.run.documents:
        if document.status != 'queued':
            continue
        if not check():
            break
        try:
            if not cfg.options().enabled or cfg.model != claimed.run.model or cfg.provider != claimed.run.provider:
                raise ImportAiError('configuration_changed', 503)
            with get_session_factory()() as session:
                source = ReadImportSourceUseCase(
                    SqlAlchemyImportJobRepositoryAdapter(session), get_file_storage(), build_zip_archive_reader()
                ).execute(UUID(claimed.run.job_id), document.file_id, claimed.user_id, claimed.role)
            result, count, checksum, usage = analyze.analyze(source.content, source.mime_type, remaining, check)
            if not save_ai_document(rid, token, document.file_id, result, count, checksum, usage):
                break
            remaining -= count
        except ImportAiError as exc:
            if exc.code == 'cancelled':
                break
            save_ai_document(rid, token, document.file_id, {}, exc.page_count, exc.checksum, exc.usage, exc.code)
            remaining -= exc.page_count
        except SQLAlchemyError:
            raise
        except Exception:
            # Исключение может содержать текст документа или адрес с секретом.
            save_ai_document(rid, token, document.file_id, {}, 0, None, {}, 'processing_error')
            logger.warning('import_ai_document_error', run_id=run_id, file_id=document.file_id)

    finish_ai_run(rid, token)


class DispatchedTask(Protocol):
    """Публикация Celery без нетипизированного task-объекта."""

    def apply_async(self, *, args: list[str]) -> object:
        """Передать только идентификатор запуска."""
        ...


def enqueue_import_ai_runs(limit: int = 100) -> int:
    """Восстановить leases и доставить готовые намерения, сохранив их при сбое Redis.

    Returns:
        Число доставленных сообщений.

    Raises:
        SQLAlchemyError: БД недоступна; следующий проход повторит доставку.
    """
    with get_session_factory()() as session:
        invalid = (
            select(ImportAiRunRow.id)
            .join(ImportJobRow, ImportJobRow.id == ImportAiRunRow.job_id)
            .join(UserRow, UserRow.id == ImportAiRunRow.user_id)
            .where(
                (ImportJobRow.status != 'needs_review')
                | (UserRow.status != 'active')
                | UserRow.role.not_in(['doctor', 'admin'])
            )
        )
        invalid_ids = session.scalars(invalid).all()
        session.execute(
            update(ImportAiDocumentRow)
            .where(ImportAiDocumentRow.run_id.in_(invalid_ids), ImportAiDocumentRow.status == 'queued')
            .values(status='cancelled', error_code='cancelled')
        )
        session.execute(
            update(ImportAiRunRow)
            .where(ImportAiRunRow.id.in_(invalid_ids), ImportAiRunRow.status.in_(AI_ACTIVE))
            .values(status='cancelled', processing_token=None, finished_at=utc_now())
        )
        session.commit()
    with get_session_factory()() as session:
        session.execute(
            update(ImportAiRunRow)
            .where(ImportAiRunRow.status == 'running', ImportAiRunRow.lease_expires_at <= utc_now())
            .values(status='queued', processing_token=None, next_delivery_at=utc_now())
        )
        session.commit()
    delivered = 0
    for _ in range(limit):
        with get_session_factory()() as session:
            row = session.scalar(
                select(ImportAiRunRow)
                .where(ImportAiRunRow.status == 'queued', ImportAiRunRow.next_delivery_at <= utc_now())
                .order_by(ImportAiRunRow.next_delivery_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if row is None:
                break
            try:
                cast(DispatchedTask, process_import_ai).apply_async(args=[str(row.id)])
                delivered += 1
            except SQLAlchemyError:
                raise
            except Exception:
                logger.warning('import_ai_dispatch_retry', run_id=str(row.id))
            row.delivery_attempts += 1
            row.next_delivery_at = utc_now() + timedelta(seconds=60)
            session.commit()
    return delivered


def start_automatic_import_ai(job_id: UUID) -> None:
    """Использовать тот же application-сценарий после обычного разбора архива.

    Raises:
        ImportAiError: Недоступный пользователь; код сохраняется в отчёте.
    """
    with get_session_factory()() as session:
        job = session.scalar(select(ImportJobRow).where(ImportJobRow.id == job_id).with_for_update())
        if job is None or job.status.value != 'needs_review' or job.report_json.get('ai_requested') is not True:
            return
        user = session.get(UserRow, job.uploaded_by_user_id)
        files = tuple(
            import_file_id(str(f['path']))
            for p in _as_dict_list(job.report_json.get('patients'))
            for g in _as_dict_list(p.get('record_groups'))
            for f in _as_dict_list(g.get('files'))
            if not f.get('is_dicom') and f.get('mime_type') in {'application/pdf', 'image/png', 'image/jpeg'}
        )
        try:
            if user is None:
                raise ImportAiError('not_found', 404)
            # UUID импорта стабилен и допустим как ключ автоматического запуска.
            ImportAiUseCase(SqlAlchemyImportAiRepository(session), get_settings().import_ai.options()).start(
                job.id, user.id, user.role.value, files, job.id, job.version
            )
            job.report_json = {**job.report_json, 'ai_requested': False}
        except ImportAiError as exc:
            job.report_json = {**job.report_json, 'ai_requested': False, 'ai_error_code': exc.code}
        session.commit()

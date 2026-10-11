"""SQLAlchemy-запуски AI с проверкой владельца импорта и идемпотентностью."""

from dataclasses import asdict
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.application.use_cases.import_jobs.documents import import_file_id
from app.application.use_cases.import_jobs.use_cases import _as_dict_list
from app.domain.import_ai import (
    AI_ACTIVE,
    AiDocument,
    AiImportFile,
    AiOptions,
    AiRun,
    AiStartContext,
    ImportAiError,
    PROMPT_VERSION,
)
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.auth.user import UserRole, UserRow, UserStatus
from app.infrastructure.db.models.import_ai import ImportAiDocumentRow, ImportAiRunRow
from app.infrastructure.db.models.medical_records.import_job import ImportJobRow

SUPPORTED_AI_MIMES = {'application/pdf', 'image/png', 'image/jpeg'}


def run_to_domain(session: Session, row: ImportAiRunRow) -> AiRun:
    """Прочитать результат без токена, содержимого запросов и ORM-объектов.

    Returns:
        Публичный запуск с результатами документов.
    """
    documents = session.scalars(
        select(ImportAiDocumentRow).where(ImportAiDocumentRow.run_id == row.id).order_by(ImportAiDocumentRow.path)
    ).all()
    return AiRun(
        str(row.id),
        str(row.job_id),
        row.status,
        row.model,
        row.provider,
        row.prompt_version,
        row.created_at.isoformat(),
        tuple(
            AiDocument(
                d.file_id,
                d.path,
                d.filename,
                d.status,
                d.page_count,
                d.checksum,
                d.result_json,
                d.error_code,
                d.usage_json,
            )
            for d in documents
        ),
    )


def require_job(session: Session, job_id: UUID, user_id: UUID, role: str, lock: bool = False) -> ImportJobRow:
    """Проверить актуальные права, при изменении захватить строку задания.

    Returns:
        Доступное задание.

    Raises:
        ImportAiError: Пользователь или задание недоступен.
    """
    user = session.get(UserRow, user_id, populate_existing=True)
    if user is None or user.status != UserStatus.ACTIVE or user.role.value != role or role not in {'doctor', 'admin'}:
        raise ImportAiError('not_found', 404)
    statement = select(ImportJobRow).where(ImportJobRow.id == job_id).execution_options(populate_existing=True)
    if lock:
        statement = statement.with_for_update()
    job = session.scalar(statement)
    if job is None or (job.uploaded_by_user_id != user_id and user.role != UserRole.ADMIN):
        raise ImportAiError('not_found', 404)
    return job


class SqlAlchemyImportAiRepository:
    """Управлять отдельными запусками, не изменяя введённые врачом поля."""

    def __init__(self, session: Session) -> None:
        """Связать операции с транзакцией вызывающего слоя."""
        self.session = session

    def start_context(self, job_id: UUID, user_id: UUID, role: str, key: UUID) -> AiStartContext:
        """Захватить импорт и прочитать актуальные факты для application.

        Returns:
            Снимок без ORM-объектов.
        """
        job = require_job(self.session, job_id, user_id, role, lock=True)
        existing = self.session.scalar(
            select(ImportAiRunRow).where(ImportAiRunRow.job_id == job_id, ImportAiRunRow.idempotency_key == key)
        )
        active = (
            self.session.scalar(
                select(ImportAiRunRow.id).where(ImportAiRunRow.job_id == job_id, ImportAiRunRow.status.in_(AI_ACTIVE))
            )
            is not None
        )
        files = tuple(
            AiImportFile(
                import_file_id(str(f.get('path') or '')),
                str(f.get('path') or ''),
                str(f.get('filename') or ''),
                str(f.get('mime_type') or ''),
                bool(f.get('is_dicom')),
            )
            for p in _as_dict_list(job.report_json.get('patients'))
            for g in _as_dict_list(p.get('record_groups'))
            for f in _as_dict_list(g.get('files'))
        )
        return AiStartContext(
            str(job.uploaded_by_user_id),
            job.status.value,
            job.version,
            files,
            run_to_domain(self.session, existing) if existing else None,
            active,
        )

    def create(self, job_id: UUID, user_id: UUID, file_ids: tuple[str, ...], key: UUID, options: AiOptions) -> AiRun:
        """Сохранить проверенный application-запрос в транзакции start_context.

        Returns:
            Новый запуск с намерением доставки.

        Raises:
            ImportAiError: Исходный импорт отсутствует.
        """
        job = self.session.get(ImportJobRow, job_id)
        if job is None:
            raise ImportAiError('not_found', 404)
        selection_hash = sha256('\n'.join(sorted(file_ids)).encode()).hexdigest()
        files = {
            import_file_id(str(f.get('path') or '')): f
            for p in _as_dict_list(job.report_json.get('patients'))
            for g in _as_dict_list(p.get('record_groups'))
            for f in _as_dict_list(g.get('files'))
        }
        run = ImportAiRunRow(
            job_id=job_id,
            user_id=user_id,
            idempotency_key=key,
            selection_hash=selection_hash,
            model=options.model,
            provider=options.provider,
            prompt_version=PROMPT_VERSION,
            options_json=asdict(options),
        )
        self.session.add(run)
        self.session.flush()
        for fid in file_ids:
            f = files[fid]
            self.session.add(
                ImportAiDocumentRow(
                    run_id=run.id,
                    file_id=fid,
                    path=str(f['path']),
                    filename=str(f['filename']),
                    mime_type=str(f['mime_type']),
                )
            )
        job.report_json = {**job.report_json, 'latest_ai_run_id': str(run.id)}
        self.session.flush()
        return run_to_domain(self.session, run)

    def get(self, job_id: UUID, run_id: UUID, user_id: UUID, role: str) -> AiRun:
        """Повторно проверить права на запуск и его исходный импорт.

        Returns:
            Результаты запуска.

        Raises:
            ImportAiError: Запуск недоступен.
        """
        require_job(self.session, job_id, user_id, role)
        row = self.session.get(ImportAiRunRow, run_id)
        if row is None or row.job_id != job_id:
            raise ImportAiError('not_found', 404)
        return run_to_domain(self.session, row)

    def cancel(self, job_id: UUID, run_id: UUID, user_id: UUID, role: str) -> AiRun:
        """Остановить анализ, сохранив уже проверенные предложения.

        Returns:
            Текущее состояние запуска.

        Raises:
            ImportAiError: Запуск недоступен.
        """
        require_job(self.session, job_id, user_id, role, lock=True)
        row = self.session.scalar(
            select(ImportAiRunRow).where(ImportAiRunRow.id == run_id, ImportAiRunRow.job_id == job_id).with_for_update()
        )
        if row is None:
            raise ImportAiError('not_found', 404)
        if row.status in AI_ACTIVE:
            row.status, row.processing_token, row.finished_at = 'cancelled', None, utc_now()
            self.session.execute(
                update(ImportAiDocumentRow)
                .where(ImportAiDocumentRow.run_id == run_id, ImportAiDocumentRow.status == 'queued')
                .values(status='cancelled', error_code='cancelled')
            )
        self.session.flush()
        return run_to_domain(self.session, row)

    def latest_documents(self, job_id: UUID, user_id: UUID, role: str) -> tuple[AiRun, ...]:
        """Прочитать завершённые предложения по доступному импорту.

        Returns:
            Запуски от новых к старым для проверки выбранных групп.
        """
        require_job(self.session, job_id, user_id, role)
        rows = self.session.scalars(
            select(ImportAiRunRow)
            .where(ImportAiRunRow.job_id == job_id)
            .order_by(ImportAiRunRow.created_at.desc(), ImportAiRunRow.id.desc())
        ).all()
        return tuple(run_to_domain(self.session, row) for row in rows)

    def list_runs(self, job_id: UUID, user_id: UUID, role: str, offset: int, limit: int) -> tuple[AiRun, ...]:
        """Получить страницу версий предложений с повторной проверкой доступа.

        Returns:
            Запуски от новых к старым.
        """
        require_job(self.session, job_id, user_id, role)
        rows = self.session.scalars(
            select(ImportAiRunRow)
            .where(ImportAiRunRow.job_id == job_id)
            .order_by(ImportAiRunRow.created_at.desc(), ImportAiRunRow.id.desc())
            .offset(offset)
            .limit(limit)
        ).all()
        return tuple(run_to_domain(self.session, row) for row in rows)

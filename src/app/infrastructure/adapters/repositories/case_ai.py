"""Хранилище сводок; клинический ACL проверяет прикладной сценарий."""

import json
from dataclasses import asdict, replace
from hashlib import sha256
from typing import cast
from uuid import UUID

from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.case_ai import CaseSummaryRun, SUMMARY_ACTIVE, SUMMARY_PROMPT_VERSION, SummaryDocument
from app.domain.import_ai import AiOptions
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.case_ai import CaseSummaryRunRow
from app.infrastructure.db.models.medical_records.file_attachment import FileAttachmentRow
from app.infrastructure.db.models.medical_records.medical_record import MedicalRecordRow

_documents = TypeAdapter(tuple[SummaryDocument, ...])


def serialize_documents(documents: tuple[SummaryDocument, ...]) -> list[dict[str, object]]:
    """Преобразовать типизированные результаты в JSON без секретов и бинарных файлов.

    Returns:
        Представление для транзакционного хранения.
    """
    return cast(list[dict[str, object]], _documents.dump_python(documents, mode='json'))


def summary_to_domain(row: CaseSummaryRunRow) -> CaseSummaryRun:
    """Собрать безопасную проекцию запуска без lease и ключей хранилища.

    Returns:
        Запуск с результатами отдельных документов.
    """
    return CaseSummaryRun(
        row.id,
        row.case_id,
        row.status,
        row.model,
        row.provider,
        row.prompt_version,
        row.created_at,
        _documents.validate_python(row.documents_json),
    )


class SqlAlchemyCaseSummaryRepository:
    """Сохранять операции в транзакции вызывающего router или worker."""

    def __init__(self, session: Session) -> None:
        """Использовать переданную сессию без внутренних commit."""
        self.session = session

    def find(self, case_id: UUID, user_id: UUID, key: UUID) -> CaseSummaryRun | None:
        """Найти запуск с тем же ключом только для автора в указанном случае.

        Returns:
            Повторный запуск либо None.
        """
        row = self.session.scalar(
            select(CaseSummaryRunRow).where(
                CaseSummaryRunRow.case_id == case_id,
                CaseSummaryRunRow.user_id == user_id,
                CaseSummaryRunRow.idempotency_key == key,
            )
        )
        return summary_to_domain(row) if row else None

    def get(self, case_id: UUID, user_id: UUID, run_id: UUID | None) -> CaseSummaryRun | None:
        """Получить свой конкретный или последний запуск без раскрытия чужой сводки.

        Returns:
            Собственный запуск либо None.
        """
        query = select(CaseSummaryRunRow).where(
            CaseSummaryRunRow.case_id == case_id, CaseSummaryRunRow.user_id == user_id
        )
        if run_id:
            query = query.where(CaseSummaryRunRow.id == run_id)
        row = self.session.scalar(query.order_by(CaseSummaryRunRow.created_at.desc(), CaseSummaryRunRow.id).limit(1))
        return summary_to_domain(row) if row else None

    def selection(self, run_id: UUID) -> tuple[UUID, ...]:
        """Вернуть первоначальный выбор независимо от наличия поддерживаемых вложений.

        Returns:
            Идентификаторы выбранных записей.
        """
        row = self.session.get(CaseSummaryRunRow, run_id)
        return tuple(UUID(s['record_id']) for s in row.sources_json) if row else ()

    def sources_current(self, run_id: UUID) -> bool:
        """Не выдавать прежние факты, если запись или её вложения изменились.

        Returns:
            Актуальность исходного снимка.
        """
        row = self.session.get(CaseSummaryRunRow, run_id)
        if row is None:
            return False
        for source in row.sources_json:
            record = self.session.get(MedicalRecordRow, UUID(source['record_id']), populate_existing=True)
            if record is None or record.updated_at.isoformat() != source['updated_at']:
                return False
            if self._attachment_hash(record.id) != source['attachment_hash']:
                return False
        return True

    def active(self, case_id: UUID, user_id: UUID) -> bool:
        """Проверить существование queued/running под блокировкой случая.

        Returns:
            True при существовании активного запуска.
        """
        return (
            self.session.scalar(
                select(CaseSummaryRunRow.id)
                .where(
                    CaseSummaryRunRow.case_id == case_id,
                    CaseSummaryRunRow.user_id == user_id,
                    CaseSummaryRunRow.status.in_(SUMMARY_ACTIVE),
                )
                .limit(1)
            )
            is not None
        )

    def create(
        self,
        case_id: UUID,
        user_id: UUID,
        key: UUID,
        record_ids: tuple[UUID, ...],
        documents: tuple[SummaryDocument, ...],
        options: AiOptions,
    ) -> CaseSummaryRun:
        """Сохранить запуск вместе с намерением доставки в PostgreSQL.

        Returns:
            Проекция нового запуска.

        Raises:
            ValueError: Проверенный источник исчез из транзакции.
        """
        sources = []
        for rid in record_ids:
            record = self.session.get(MedicalRecordRow, rid)
            if record is None:
                raise ValueError('Missing authorized source')
            sources.append(
                {
                    'record_id': str(rid),
                    'updated_at': record.updated_at.isoformat(),
                    'attachment_hash': self._attachment_hash(rid),
                }
            )
        row = CaseSummaryRunRow(
            case_id=case_id,
            user_id=user_id,
            idempotency_key=key,
            status='queued',
            model=options.model,
            provider=options.provider,
            prompt_version=SUMMARY_PROMPT_VERSION,
            options_json=asdict(options),
            sources_json=sources,
            documents_json=serialize_documents(documents),
        )
        self.session.add(row)
        self.session.flush()
        return summary_to_domain(row)

    def cancel(self, run_id: UUID) -> CaseSummaryRun:
        """Заблокировать попытку и пометить только оставшиеся документы отменёнными.

        Returns:
            Актуальное состояние после отмены.
        """
        row = self.session.scalars(
            select(CaseSummaryRunRow)
            .where(CaseSummaryRunRow.id == run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one()
        if row.status in SUMMARY_ACTIVE:
            run = summary_to_domain(row)
            row.documents_json = serialize_documents(
                tuple(
                    replace(d, status='cancelled', error_code='cancelled') if d.status == 'queued' else d
                    for d in run.documents
                )
            )
            row.status, row.processing_token, row.finished_at = 'cancelled', None, utc_now()
        return summary_to_domain(row)

    def _attachment_hash(self, record_id: UUID) -> str:
        files = self.session.scalars(
            select(FileAttachmentRow)
            .where(
                FileAttachmentRow.record_id == record_id,
                FileAttachmentRow.comment_id.is_(None),
            )
            .order_by(FileAttachmentRow.id)
        ).all()
        raw = [(str(f.id), f.storage_key, f.mime_type, f.size_bytes) for f in files]
        return sha256(json.dumps(raw).encode()).hexdigest()

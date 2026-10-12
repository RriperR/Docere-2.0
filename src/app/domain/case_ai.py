"""Фактическая сводка выбранных материалов без изменения медицинской истории."""

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from app.domain.import_ai import AiSource

SUMMARY_PROMPT_VERSION = 'case-facts-v1'
SUMMARY_ACTIVE = {'queued', 'running'}
SUMMARY_MIME_TYPES = {'application/pdf', 'image/png', 'image/jpeg'}


@dataclass(frozen=True, slots=True)
class SummaryFact:
    """Один факт или указанное в документе назначение с источниками."""

    text: str
    category: Literal['fact', 'mentioned_care']
    sources: tuple[AiSource, ...]


@dataclass(frozen=True, slots=True)
class SummaryExtraction:
    """Извлечённые сведения одного пакета страниц."""

    facts: tuple[SummaryFact, ...]
    issues: tuple[str, ...]
    event_date: date | None = None
    multiple_patients: bool = False
    patient_name: str | None = None
    patient_birth_date: date | None = None


@dataclass(frozen=True, slots=True)
class SummaryDocument:
    """Результат одного вложения с проверяемой ссылкой на материал случая."""

    record_id: UUID
    attachment_id: UUID | None
    title: str
    record_date: date
    filename: str
    mime_type: str
    status: str = 'queued'
    facts: tuple[SummaryFact, ...] = ()
    issues: tuple[str, ...] = ()
    document_date: date | None = None
    page_count: int = 0
    checksum: str | None = None
    error_code: str | None = None
    usage: dict[str, int] | None = None


@dataclass(frozen=True, slots=True)
class CaseSummaryRun:
    """Личная сводка врача; чтение требует полного доступа к исходному случаю."""

    id: UUID
    case_id: UUID
    status: str
    model: str
    provider: str
    prompt_version: str
    created_at: datetime
    documents: tuple[SummaryDocument, ...]


def merge_summary_batches(batches: list[SummaryExtraction]) -> SummaryExtraction:
    """Сохранить все факты с источниками и не выбирать произвольную дату.

    Args:
        batches: Результаты всех пакетов одного документа.

    Returns:
        Факты без дублей и явные проблемы распознавания.
    """
    grouped: dict[tuple[str, str], SummaryFact] = {}
    for batch in batches:
        for fact in batch.facts:
            key = (fact.category, ' '.join(fact.text.casefold().split()))
            previous = grouped.get(key)
            grouped[key] = (
                replace(previous, sources=tuple(dict.fromkeys(previous.sources + fact.sources))) if previous else fact
            )
    facts = tuple(grouped.values())
    issues = tuple(dict.fromkeys(issue for batch in batches for issue in batch.issues))
    dates = {batch.event_date for batch in batches if batch.event_date is not None}
    if len(dates) > 1:
        issues += ('conflicting:event_date',)
    event_date = next(iter(dates)) if len(dates) == 1 and 'conflicting:event_date' not in issues else None
    names = {' '.join(b.patient_name.casefold().split()) for b in batches if b.patient_name}
    births = {b.patient_birth_date for b in batches if b.patient_birth_date}
    patient_conflict = any(b.multiple_patients for b in batches) or len(names) > 1 or len(births) > 1
    return SummaryExtraction(facts, issues, event_date, patient_conflict)

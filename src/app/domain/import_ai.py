"""Проверенные предложения AI без автоматического изменения медицинской истории."""

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Literal

AiFieldName = Literal['fio', 'date_of_birth', 'event_date', 'record_type', 'title', 'clinical_summary']
AI_FIELDS = {'fio', 'date_of_birth', 'event_date', 'record_type', 'title', 'clinical_summary'}
AI_ACTIVE = {'queued', 'running'}
PROMPT_VERSION = 'import-facts-v1'


class ImportAiError(Exception):
    """Безопасная ошибка AI-импорта для API и worker."""

    def __init__(self, code: str, status: int = 422) -> None:
        """Сохранить код без текста документа или ответа провайдера.

        Args:
            code: Стабильный код ошибки.
            status: HTTP-статус транспортной границы.
        """
        super().__init__(code)
        self.code, self.status = code, status
        self.page_count = 0
        self.checksum: str | None = None
        self.usage: dict[str, int] = {}


@dataclass(frozen=True, slots=True)
class AiSource:
    """Страница и фрагмент, указанные моделью как источник факта."""

    page: int
    excerpt: str


@dataclass(frozen=True, slots=True)
class AiField:
    """Предлагаемое значение с источниками для ручной проверки."""

    value: str
    sources: tuple[AiSource, ...]


@dataclass(frozen=True, slots=True)
class AiExtraction:
    """Проверенный результат отдельного пакета страниц."""

    fields: dict[str, AiField]
    issues: tuple[str, ...] = ()
    multiple_patients: bool = False


def merge_extractions(batches: list[AiExtraction]) -> dict[str, object]:
    """Объединить совпадающие факты и выделить противоречия.

    Args:
        batches: Ответы по страницам одного документа.

    Returns:
        Предложения с источниками и явными проблемами.
    """
    merged: dict[str, object] = {}
    issues = list(dict.fromkeys(issue for batch in batches for issue in batch.issues))
    patient_conflict = any(b.multiple_patients for b in batches)
    for name in sorted(AI_FIELDS):
        fields = [b.fields[name] for b in batches if name in b.fields]
        if not fields:
            issues.append('missing:' + name)
            continue
        unique = {f.value.strip().casefold() for f in fields}
        if len(unique) > 1 and name != 'clinical_summary':
            issues.append('conflicting:' + name)
            patient_conflict |= name in {'fio', 'date_of_birth'}
            continue
        value = fields[0].value if name != 'clinical_summary' else '\n'.join(dict.fromkeys(f.value for f in fields))
        sources = tuple(dict.fromkeys(source for f in fields for source in f.sources))
        merged[name] = {'value': value[:10000], 'sources': [asdict(s) for s in sources]}
    return {
        'fields': merged,
        'issues': list(dict.fromkeys(issues)),
        'patient_conflict': patient_conflict,
        'multiple_patients': any(b.multiple_patients for b in batches),
    }


def validate_field(name: str, value: str) -> None:
    """Проверить значения независимо от доверия к модели.

    Args:
        name: Имя разрешённого поля.
        value: Предложенное значение.

    Raises:
        ImportAiError: Значение некорректно.
    """
    if name not in AI_FIELDS or not value.strip() or len(value) > (10000 if name == 'clinical_summary' else 255):
        raise ImportAiError('invalid_response')
    if name in {'date_of_birth', 'event_date'}:
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ImportAiError('invalid_response') from exc
        if parsed.isoformat() != value:
            raise ImportAiError('invalid_response')
    if name == 'record_type' and value not in {'consultation_result', 'exam_result', 'lab_result', 'other'}:
        raise ImportAiError('invalid_response')


@dataclass(frozen=True, slots=True)
class AiOptions:
    """Не секретные ограничения и идентификация настроенной модели."""

    enabled: bool = False
    provider: str = 'AI-сервис'
    model: str = ''
    max_documents: int = 20
    max_pages: int = 100
    max_pages_per_document: int = 30
    batch_pages: int = 5
    concurrency: int = 2


@dataclass(frozen=True, slots=True)
class AiDocument:
    """Результат или состояние одного исходника."""

    file_id: str
    path: str
    filename: str
    status: str
    page_count: int = 0
    checksum: str | None = None
    result: dict[str, object] = field(default_factory=dict)
    error_code: str | None = None
    usage: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AiRun:
    """Публичное состояние запуска без ключа провайдера."""

    id: str
    job_id: str
    status: str
    model: str
    provider: str
    prompt_version: str
    created_at: str
    documents: tuple[AiDocument, ...]


@dataclass(frozen=True, slots=True)
class AiImportFile:
    """Исходник, доступный для выбора в проверяемом импорте."""

    id: str
    path: str
    filename: str
    mime_type: str
    is_dicom: bool


@dataclass(frozen=True, slots=True)
class AiStartContext:
    """Снимок импорта под транзакционной блокировкой."""

    owner_id: str
    status: str
    version: int
    files: tuple[AiImportFile, ...]
    repeated_run: AiRun | None
    active: bool

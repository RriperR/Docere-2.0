"""Метрики E2 и ручная сверка пересказа; без альтернативного LLM-эталона."""

import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
from time import perf_counter
from typing import cast, Literal, NotRequired, TypedDict

from scripts.import_ai_dataset import Document, Page, Source

from app.application.ports.import_jobs.ai import DocumentPage, ImportAiProviderPort
from app.domain.import_ai import AiExtraction, ImportAiError, validate_field
from app.infrastructure.adapters.import_jobs.ai_provider import parse_extraction

EVALUATOR_VERSION = 'import-evaluation-e2-v1'
GRADES = {'confirmed', 'unsupported', 'contradicted'}


class CheckedField(TypedDict):
    """Проверенное поле существующего production parser."""

    value: str
    sources: list[Source]


class CheckedResult(TypedDict, total=False):
    """Результат merge_extractions либо пустой результат отказа."""

    fields: dict[str, CheckedField]
    issues: list[str]
    multiple_patients: bool
    patient_conflict: bool


class RequestMeasurement(TypedDict):
    """Измерение extract, без raw response и секретов."""

    pages: list[int]
    usage: dict[str, int]
    error_code: str | None
    elapsed_seconds: float | None


class DocumentMetrics(TypedDict):
    """Счётчики и обнаруженные автоматические ошибки."""

    counts: dict[str, int]
    failures: list[str]


class EvaluationRow(TypedDict):
    """Проверенный анализ одного документа и телеметрия его пакетов."""

    document: str
    split: str
    sha256: str
    expected_error: str | None
    error_code: str | None
    result: CheckedResult
    pages: int
    usage: dict[str, int]
    calls: list[RequestMeasurement]
    elapsed_seconds: NotRequired[float | None]
    metrics: NotRequired[DocumentMetrics]


Grade = Literal['confirmed', 'unsupported', 'contradicted']


class ReviewEvidence(TypedDict):
    """Неизменяемое утверждение и его исходные ссылки."""

    id: str
    document: str
    claim: str
    sources: list[Source]
    note: str


class ClaimReview(ReviewEvidence):
    """Ручная оценка фактической поддержки утверждения."""

    grade: Grade | None


class FactReview(ReviewEvidence):
    """Ручная оценка присутствия ожидаемого факта в пересказе."""

    required: bool
    present: bool | None


class ManualReview(TypedDict):
    """Разметка, относящаяся к одному конкретному результату."""

    schema_version: int
    run_id: str
    reviewer: str | None
    claims: list[ClaimReview]
    facts: list[FactReview]


class ManualMetrics(TypedDict):
    """Счётчики ручной оценки с явными незавершёнными строками."""

    basis: str
    reviewer: str | None
    claims_total: int
    claim_grades: dict[str, int]
    required_facts_total: int
    required_facts_pending: int
    missing_required_facts_reviewed: int
    missing_required_facts: int | None
    status: str


class Tariff(TypedDict):
    """Известная цена с валютой и ссылкой на тариф."""

    input_per_million: float
    output_per_million: float
    currency: str
    reference: str


class CostEstimate(TypedDict):
    """Стоимость при полной usage либо отсутствие данных."""

    amount: float | None
    status: str
    tariff: NotRequired[Tariff]


class Accuracy(TypedDict):
    """Доля с явным числителем и знаменателем."""

    correct: int
    total: int
    ratio: float | None


class FailedExample(TypedDict):
    """Документ и конкретные автоматические проверки, которые не прошли."""

    document: str
    failures: list[str]


class AutomaticMetrics(TypedDict):
    """Суммарные метрики фиксированного выбранного набора."""

    counts: dict[str, int]
    filled_field_accuracy: Accuracy
    field_slot_accuracy: Accuracy
    correct_abstention: Accuracy
    correct_ambiguity: Accuracy
    document_errors: int
    unexpected_document_errors: int
    partial_document_errors: int
    failed_examples: list[FailedExample]


class ProviderParameters(TypedDict):
    """Несекретные параметры измерения существующего provider."""

    latency_basis: str
    timeout_seconds: NotRequired[float]
    disable_thinking: NotRequired[bool]


class ExecutionParameters(TypedDict):
    """Порядок обхода и бюджет evaluator, отдельно от production bulk run."""

    order: str
    concurrency: int
    page_budget: str
    request_parameters: str


class EvaluationMetadata(TypedDict):
    """Версии и параметры, определяющие идентичность прогона."""

    schema_version: int
    evaluator_version: str
    mode: str
    quality_evidence: str
    status: str
    dataset_version: str
    selected_split: str
    manifest_sha256: str
    model: str
    prompt_version: str
    prompt_sha256: str
    options: dict[str, str | int | bool]
    provider_parameters: ProviderParameters
    execution_parameters: ExecutionParameters
    documents_total: int
    synthetic_only: bool


class RequestTelemetry(TypedDict):
    """Агрегат доступной телеметрии без выдуманных HTTP attempts."""

    extract_calls: int
    failed_extract_calls: int
    usage_available_calls: int
    usage: dict[str, int]
    elapsed_seconds: list[float | None] | None
    http_attempt_count: None


class EvaluationReport(EvaluationMetadata):
    """Полный machine-readable результат E2."""

    run_id: str
    documents: list[EvaluationRow]
    automatic: AutomaticMetrics
    manual: ManualMetrics
    request_telemetry: RequestTelemetry
    cost: CostEstimate
    limitations: list[str]


def document_pages(document: Document) -> list[Page]:
    """Взять типизированные исходные страницы E1 из общего recipe-контракта.

    Returns:
        Исходные страницы с явно заданными номерами.

    Raises:
        ValueError: Документ не содержит пронумерованные страницы E1.
    """
    if any(isinstance(page, str) for page in document['pages']):
        raise ValueError('Evaluation requires numbered E1 pages')
    return cast(list[Page], list(document['pages']))


def canonical_hash(value: object) -> str:
    """Получить идентификатор JSON независимо от порядка ключей.

    Returns:
        SHA-256 канонического JSON.
    """
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class ControlledProvider:
    """Возвращать эталонные фикстуры; не распознавать документ и не измерять модель."""

    def __init__(self, document: Document) -> None:
        """Связать один синтетический документ с ответами по пакетам страниц."""
        self.document = document

    def extract(self, pages: tuple[DocumentPage, ...]) -> tuple[AiExtraction, dict[str, int]]:
        """Пропустить известные ответы через существующий production parser.

        Returns:
            Проверенное извлечение и пустая usage: токены не измерялись.
        """
        expected = self.document['expected']
        numbers = {page.number for page in pages}
        fields: dict[str, CheckedField] = {}
        for name, field in expected['fields'].items():
            sources = [s for s in field['sources'] if s['page'] in numbers]
            values = [v for v in field['allowed_values'] if v is not None]
            if sources and values:
                fields[name] = {'value': values[0], 'sources': sources}
        facts = [f for f in expected['facts'] if any(s['page'] in numbers for s in f['sources'])]
        if facts:
            fields['clinical_summary'] = {
                'value': '\n'.join(f['claim'] for f in facts),
                'sources': [s for f in facts for s in f['sources'] if s['page'] in numbers],
            }
        payload = {
            'fields': fields,
            'issues': expected['issues'],
            'ambiguous_fields': [s.split(':', 1)[1] for s in expected['issues'] if s.startswith('conflicting:')],
            'multiple_patients': expected['multiple_patients'],
        }
        return parse_extraction(json.dumps(payload), pages), {}


class MeasuredProvider:
    """Измерять один extract, включая встроенные повторы, без записи сырого ответа."""

    def __init__(self, provider: ImportAiProviderPort, live: bool) -> None:
        """Сохранить adapter и признак реального измерения времени."""
        self.provider, self.live = provider, live
        self.calls: list[RequestMeasurement] = []

    def extract(self, pages: tuple[DocumentPage, ...]) -> tuple[AiExtraction, dict[str, int]]:
        """Сохранить страницы, доступную usage и безопасный код отказа.

        Returns:
            Извлечение и usage исходного adapter.
        """
        start = perf_counter()
        call: RequestMeasurement = {
            'pages': [p.number for p in pages],
            'usage': {},
            'error_code': None,
            'elapsed_seconds': None,
        }
        try:
            result, usage = self.provider.extract(pages)
            call['usage'] = usage
            return result, usage
        except Exception as exc:
            call['error_code'] = exc.code if isinstance(exc, ImportAiError) else 'unexpected_error'
            raise
        finally:
            # Офлайн отчёт воспроизводим: никакую фиктивную latency не выдаём за измерение.
            call['elapsed_seconds'] = round(perf_counter() - start, 6) if self.live else None
            self.calls.append(call)


def score_document(document: Document, row: EvaluationRow) -> DocumentMetrics:
    """Подсчитать точные реквизиты, отказ и структурные ошибки источников.

    Args:
        document: Синтетический эталон E1.
        row: Проверенный результат или безопасная ошибка анализа.

    Returns:
        Счётчики с явными знаменателями; смысл источника оценивается вручную.
    """
    expected = document['expected']
    result = row['result']
    fields = result.get('fields', {})
    expected_error = expected['error_code']
    error_ok = row['error_code'] == expected_error
    metrics: Counter[str] = Counter(
        dict.fromkeys(
            (
                'invalid_response_errors',
                'format_errors',
                'page_errors',
                'excerpt_errors',
                'missing_source_fields',
                'excerpt_not_verbatim',
                'document_page_count_errors',
                'missing_required_fields',
                'missing_required_facts_without_summary',
            ),
            0,
        )
    )
    summary = fields.get('clinical_summary')
    if summary is None or not summary['value'].strip():
        metrics['missing_required_facts_without_summary'] = sum(fact['required'] for fact in expected['facts'])
    metrics['invalid_response_errors'] += row['error_code'] == 'invalid_response'
    failures = []
    if row['error_code'] is None and row.get('pages', len(document['pages'])) != len(document['pages']):
        metrics['document_page_count_errors'] += 1
        failures.append('document_page_count_errors')
    if not error_ok:
        failures.append('unexpected_error' if row['error_code'] else 'missing_expected_error')
    metrics['error_outcomes_checked'] += 1
    metrics['error_outcomes_correct'] += error_ok
    for name, reference in expected['fields'].items():
        field_value = fields.get(name)
        actual = field_value['value'] if field_value is not None else None
        metrics['field_slots'] += 1
        metrics['field_slots_correct'] += actual in reference['allowed_values']
        if actual is not None:
            metrics['filled_reference_fields'] += 1
            metrics['filled_reference_fields_correct'] += actual in reference['allowed_values']
        elif None not in reference['allowed_values']:
            metrics['missing_required_fields'] += 1
        if actual not in reference['allowed_values']:
            failures.append('field:' + name)
    for name in expected['empty_fields']:
        metrics['empty_fields_checked'] += 1
        present = name in fields
        metrics['empty_fields_correct'] += not present
        if present:
            metrics['filled_reference_fields'] += 1
            failures.append('expected_empty:' + name)
    issues = result.get('issues', [])
    for issue in expected['issues']:
        name = issue.split(':', 1)[-1]
        ok = issue in issues and (not issue.startswith('conflicting:') or name not in fields)
        metrics['ambiguity_checks'] += 1
        metrics['ambiguity_correct'] += ok
        if not ok:
            failures.append('issue:' + issue)
    if expected_error is None:
        metrics['patient_checks'] += 1
        patient_ok = result.get('multiple_patients', False) == expected['multiple_patients']
        metrics['patient_checks_correct'] += patient_ok
        if not patient_ok:
            failures.append('multiple_patients')
    source_pages = {page['number']: ' '.join(page['text'].split()) for page in document_pages(document)}
    for name, field in fields.items():
        try:
            validate_field(name, field['value'])
        except (ImportAiError, KeyError, TypeError):
            metrics['format_errors'] += 1
        sources = field.get('sources', [])
        if not sources:
            metrics['missing_source_fields'] += 1
        for source in sources:
            metrics['sources_checked'] += 1
            page = source.get('page')
            if isinstance(page, bool) or not isinstance(page, int) or page not in source_pages:
                metrics['page_errors'] += 1
            elif not isinstance(source.get('excerpt'), str) or not source['excerpt'].strip():
                metrics['excerpt_errors'] += 1
            elif ' '.join(source['excerpt'].split()) not in source_pages[page]:
                # Только лексический сигнал: OCR/перевод могут быть корректны. Не оценка смысла.
                metrics['excerpt_not_verbatim'] += 1
    for key in (
        'format_errors',
        'page_errors',
        'missing_source_fields',
        'excerpt_errors',
        'missing_required_facts_without_summary',
    ):
        if metrics[key]:
            failures.append(key)
    return {'counts': dict(metrics), 'failures': failures}


def review_template(rows: Sequence[EvaluationRow], documents: Sequence[Document], run_id: str) -> ManualReview:
    """Подготовить ручную таблицу утверждений и полноты, не назначая оценки.

    Returns:
        Шаблон JSON с оценками None и привязкой к результату.
    """
    review: ManualReview = {'schema_version': 1, 'run_id': run_id, 'reviewer': None, 'claims': [], 'facts': []}
    for row, document in zip(rows, documents, strict=True):
        summary = row['result'].get('fields', {}).get('clinical_summary')
        summary_text = summary['value'] if summary else ''
        summary_sources = summary['sources'] if summary else []
        # Границы предложений являются подсказкой: эксперт проверяет составные утверждения целиком.
        claims = [s.strip() for s in re.split(r'\n+|(?<=[.!?])\s+', summary_text) if s.strip()]
        for index, claim in enumerate(claims, 1):
            review['claims'].append(
                {
                    'id': f'{document["name"]}:claim-{index}',
                    'document': document['name'],
                    'claim': claim,
                    'sources': summary_sources,
                    'grade': None,
                    'note': '',
                }
            )
        for fact in document['expected']['facts']:
            review['facts'].append(
                {
                    'id': fact['id'],
                    'document': document['name'],
                    'claim': fact['claim'],
                    'sources': fact['sources'],
                    'required': fact['required'],
                    'present': None,
                    'note': '',
                }
            )
    return review


def _validate_review_rows(
    template: Sequence[Mapping[str, object]],
    annotations: Sequence[Mapping[str, object]],
    key: str,
    allowed: Sequence[object],
) -> None:
    originals = {item['id']: item for item in template}
    if len(annotations) != len(originals) or {item['id'] for item in annotations} != set(originals):
        raise ValueError('Manual review must contain exactly the expected IDs')
    for item in annotations:
        if canonical_hash({k: v for k, v in item.items() if k not in {key, 'note'}}) != canonical_hash(
            {k: v for k, v in originals[item['id']].items() if k not in {key, 'note'}}
        ):
            raise ValueError('Manual review changed immutable evidence')
        value = item.get(key)
        if value not in allowed or (key == 'present' and value is not None and type(value) is not bool):
            raise ValueError('Invalid manual grade')


def manual_metrics(template: ManualReview, annotations: ManualReview | None = None) -> ManualMetrics:
    """Подсчитать экспертную оценку; отклонить чужую/устаревшую разметку.

    Returns:
        Счётчики только ручных оценок и незавершённой разметки.

    Raises:
        ValueError: Разметка не относится к результату или содержит неизвестные оценки.
    """
    if annotations is None:
        annotations = template
    if annotations.get('schema_version') != template['schema_version']:
        raise ValueError('Manual review schema version does not match')
    if annotations.get('run_id') != template['run_id']:
        raise ValueError('Manual review run_id does not match this result')
    has_annotations = any(item.get('grade') is not None for item in annotations.get('claims', [])) or any(
        item.get('present') is not None for item in annotations.get('facts', [])
    )
    reviewer = annotations.get('reviewer')
    if has_annotations and (not isinstance(reviewer, str) or not reviewer.strip()):
        raise ValueError('Manual annotations require a reviewer')
    _validate_review_rows(template['claims'], annotations['claims'], 'grade', (*GRADES, None))
    _validate_review_rows(template['facts'], annotations['facts'], 'present', (True, False, None))
    claims: Counter[str] = Counter(item['grade'] or 'pending' for item in annotations['claims'])
    required = [item for item in annotations['facts'] if item['required']]
    pending = sum(item['present'] is None for item in required)
    omissions = sum(item['present'] is False for item in required)
    return {
        'basis': 'human_annotations_only',
        'reviewer': annotations.get('reviewer'),
        'claims_total': len(annotations['claims']),
        'claim_grades': dict(claims),
        'required_facts_total': len(required),
        'required_facts_pending': pending,
        'missing_required_facts_reviewed': omissions,
        'missing_required_facts': None if pending else omissions,
        'status': 'pending' if pending or claims['pending'] else 'complete',
    }


def cost_estimate(calls: Sequence[RequestMeasurement], tariff: Tariff | None = None) -> CostEstimate:
    """Рассчитать стоимость только при заданном тарифе и полной token usage.

    Returns:
        Оценка с источником тарифа либо no_data.
    """
    if (
        not tariff
        or not calls
        or any(not {'prompt_tokens', 'completion_tokens'} <= call['usage'].keys() for call in calls)
    ):
        return {'amount': None, 'status': 'no_data'}
    amount = (
        sum(
            call['usage']['prompt_tokens'] * tariff['input_per_million']
            + call['usage']['completion_tokens'] * tariff['output_per_million']
            for call in calls
        )
        / 1_000_000
    )
    return {'amount': amount, 'status': 'estimated', 'tariff': tariff}


def aggregate(rows: Sequence[EvaluationRow]) -> AutomaticMetrics:
    """Суммировать явные знаменатели и частичные отказы, сохраняя неудачные примеры.

    Returns:
        Счётчики, доли, список проблемных документов.
    """
    totals: Counter[str] = Counter()
    for row in rows:
        totals.update(row['metrics']['counts'])

    def ratio(numerator: str, denominator: str) -> Accuracy:
        return {
            'correct': totals[numerator],
            'total': totals[denominator],
            'ratio': totals[numerator] / totals[denominator] if totals[denominator] else None,
        }

    return {
        'counts': dict(totals),
        'filled_field_accuracy': ratio('filled_reference_fields_correct', 'filled_reference_fields'),
        'field_slot_accuracy': ratio('field_slots_correct', 'field_slots'),
        'correct_abstention': ratio('empty_fields_correct', 'empty_fields_checked'),
        'correct_ambiguity': ratio('ambiguity_correct', 'ambiguity_checks'),
        'document_errors': sum(row['error_code'] is not None for row in rows),
        'unexpected_document_errors': sum(
            bool(row['error_code']) and row['error_code'] != row['expected_error'] for row in rows
        ),
        'partial_document_errors': sum(
            bool(row['error_code']) and any(call['error_code'] is None for call in row['calls']) for row in rows
        ),
        'failed_examples': [
            {'document': row['document'], 'failures': row['metrics']['failures']}
            for row in rows
            if row['metrics']['failures']
        ],
    }


def review_markdown(review: ManualReview) -> str:
    """Представить ту же ручную разметку в таблице Markdown.

    Returns:
        Таблицы утверждений и обязательных фактов.
    """

    def cell(value: object) -> str:
        return str(value).replace('|', '\\|').replace('\n', '<br>')

    lines = [
        '# Ручная сверка синтетического пересказа E2',
        '',
        f'Run ID: `{review["run_id"]}`. Рецензент: {review.get("reviewer") or "не назначен"}.',
        '',
        'Оценки: confirmed = подтверждено; unsupported = не подтверждено; contradicted = противоречит.',
        'Пустая оценка означает ожидание ручной проверки. Источники указаны моделью для всего пересказа;',
        'рецензент проверяет каждое утверждение по исходным pages в manifest, включая составные фразы.',
        '',
        '| ID | Утверждение | Источник (страница: фрагмент) | Ручная оценка |',
        '|---|---|---|---|',
    ]
    for item in review['claims']:
        sources = '; '.join(f'{s["page"]}: {s["excerpt"]}' for s in item['sources'])
        lines.append(
            f'| {cell(item["id"])} | {cell(item["claim"])} | {cell(sources)} | '
            f'{cell(item["grade"] or "ожидает проверки")} |'
        )
    lines += [
        '',
        '## Полнота обязательных фактов',
        '',
        '| ID | Ожидаемый факт | Источник | Обязателен | Есть в пересказе |',
        '|---|---|---|---|---|',
    ]
    for fact_row in review['facts']:
        sources = '; '.join(f'{s["page"]}: {s["excerpt"]}' for s in fact_row['sources'])
        lines.append(
            f'| {cell(fact_row["id"])} | {cell(fact_row["claim"])} | {cell(sources)} | '
            f'{fact_row["required"]} | {fact_row["present"]} |'
        )
    return '\n'.join(lines) + '\n'

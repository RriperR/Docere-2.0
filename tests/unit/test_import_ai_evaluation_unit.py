"""E2: evaluator не выдаёт фикстуры/автосверку за доказательство качества модели."""

import json
import sys
from copy import deepcopy
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.evaluate_import_ai import evaluate, main, save_report  # noqa: E402
from scripts.import_ai_dataset import load_manifest  # noqa: E402
from scripts.import_ai_evaluation import (  # noqa: E402
    aggregate,
    ControlledProvider,
    cost_estimate,
    manual_metrics,
    MeasuredProvider,
    review_template,
    score_document,
)

from app.application.ports.import_jobs.ai import DocumentPage
from app.domain.import_ai import ImportAiError

DOCUMENTS = load_manifest()['documents']


def document(name='text-report.pdf'):
    return deepcopy(next(item for item in DOCUMENTS if item['name'] == name))


def row_for(item):
    provider = ControlledProvider(item)
    parsed, _ = provider.extract(tuple(DocumentPage(p['number'], p['text'], '') for p in item['pages']))
    from app.domain.import_ai import merge_extractions

    return {
        'document': item['name'],
        'result': merge_extractions([parsed]),
        'pages': len(item['pages']),
        'error_code': None,
        'expected_error': item['expected']['error_code'],
        'calls': [],
    }


def test_offline_report_is_reproducible_and_never_reads_settings_or_network(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail('Offline evaluator must not read settings or use network')

    monkeypatch.setattr('app.infrastructure.config.settings.get_settings', forbidden)
    monkeypatch.setattr(httpx.Client, 'send', forbidden)
    first, review = evaluate(tmp_path / 'first')
    second, second_review = evaluate(tmp_path / 'second')
    assert first == second and review == second_review
    assert first['status'] == 'prepared_external'
    assert first['quality_evidence'] == 'harness_only_not_model_quality'
    assert first['documents_total'] == 24
    assert first['automatic']['document_errors'] == 2
    assert first['automatic']['failed_examples'] == []
    assert first['request_telemetry']['usage_available_calls'] == 0
    assert first['request_telemetry']['elapsed_seconds'] is None
    assert first['cost'] == {'amount': None, 'status': 'no_data'}
    assert first['manual']['missing_required_facts'] is None
    assert first['manual']['status'] == 'pending'
    save_report(tmp_path / 'first', first, review)
    assert 'Утверждение' in (tmp_path / 'first/manual-review.md').read_text()
    assert first == json.loads((tmp_path / 'first/results.json').read_text())


@pytest.mark.parametrize('split,count', [('development', 15), ('holdout', 9)])
def test_split_limits_documents_before_provider_calls(tmp_path, split, count):
    report, _ = evaluate(tmp_path / split, split)
    assert len(report['documents']) == count
    assert all(row['split'] == split for row in report['documents'])


def test_wrong_missing_and_unwarranted_fields_are_not_hidden_by_precision():
    item = document('no-date.png')
    row = row_for(item)
    row['result']['fields'].pop('date_of_birth')
    row['result']['fields']['fio']['value'] = 'Wrong Person'
    row['result']['fields']['event_date'] = {'value': '2020-01-01', 'sources': [{'page': 1, 'excerpt': 'invented'}]}
    row['metrics'] = score_document(item, row)
    metrics = aggregate([row])
    assert metrics['filled_field_accuracy'] == {'correct': 0, 'total': 2, 'ratio': 0.0}
    assert metrics['field_slot_accuracy']['ratio'] == 0.0
    assert metrics['counts']['missing_required_fields'] == 1
    assert metrics['correct_abstention']['correct'] == 0
    assert metrics['counts']['excerpt_not_verbatim'] == 1
    assert len(metrics['failed_examples']) == 1


def test_format_page_and_empty_excerpt_errors_are_distinct():
    item = document()
    row = row_for(item)
    row['result']['fields']['event_date'] = {'value': '2026-02-31', 'sources': [{'page': 99, 'excerpt': 'date'}]}
    row['result']['fields']['fio']['sources'] = [{'page': True, 'excerpt': 'name'}, {'page': 1, 'excerpt': ''}]
    row['result']['fields']['clinical_summary']['sources'] = []
    metrics = score_document(item, row)['counts']
    assert metrics['format_errors'] == 1
    assert metrics['page_errors'] == 2
    assert metrics['excerpt_errors'] == 1
    assert metrics['missing_source_fields'] == 1


def test_ambiguity_requires_both_abstention_and_issue():
    item = document('ambiguous-holdout.pdf')
    row = row_for(item)
    row['result']['issues'] = []
    assert score_document(item, row)['counts']['ambiguity_correct'] == 0
    row['result']['issues'] = ['conflicting:event_date']
    row['result']['fields']['event_date'] = {'value': '2026-01-01', 'sources': [{'page': 1, 'excerpt': 'date'}]}
    assert score_document(item, row)['counts']['ambiguity_correct'] == 0


def test_manual_omissions_and_grades_have_no_automatic_semantic_score():
    item = document('multipage-discharge.pdf')
    row = row_for(item)
    template = review_template([row], [item], 'run-1')
    assert manual_metrics(template)['missing_required_facts'] is None
    annotation = deepcopy(template)
    annotation['reviewer'] = 'Unit test annotation fixture, not a real reviewer'
    for claim, grade in zip(annotation['claims'], ['confirmed', 'unsupported', 'contradicted'], strict=True):
        claim['grade'] = grade
    for fact in annotation['facts']:
        fact['present'] = fact['id'].endswith('fact-1')
    metrics = manual_metrics(template, annotation)
    assert metrics['basis'] == 'human_annotations_only'
    assert metrics['missing_required_facts'] == 2
    assert metrics['claim_grades'] == {'confirmed': 1, 'unsupported': 1, 'contradicted': 1}
    assert metrics['status'] == 'complete'


@pytest.mark.parametrize('change', ['run', 'claim', 'source', 'id', 'grade', 'reviewer', 'truthy_integer'])
def test_manual_review_rejects_stale_or_changed_evidence(change):
    item = document()
    template = review_template([row_for(item)], [item], 'run-1')
    annotation = deepcopy(template)
    annotation['reviewer'] = 'Test annotation fixture'
    annotation['claims'][0]['grade'] = 'confirmed'
    if change == 'run':
        annotation['run_id'] = 'other-run'
    elif change == 'claim':
        annotation['claims'][0]['claim'] = 'changed'
    elif change == 'source':
        annotation['claims'][0]['sources'][0]['page'] = 99
    elif change == 'id':
        annotation['facts'][0]['id'] = 'unknown'
    elif change == 'grade':
        annotation['claims'][0]['grade'] = 'LLM said yes'
    elif change == 'reviewer':
        annotation['reviewer'] = None
    else:
        annotation['facts'][0]['present'] = 1
    with pytest.raises(ValueError):
        manual_metrics(template, annotation)


def test_partial_error_retains_calls_usage_and_safe_error_without_raw_body():
    class PartialProvider:
        def extract(self, pages):
            if pages[0].number == 2:
                raise ImportAiError('provider_unavailable', 503)
            return ControlledProvider(document()).extract(pages)[0], {'prompt_tokens': 10}

    provider = MeasuredProvider(PartialProvider(), live=False)
    provider.extract((DocumentPage(1, '', ''),))
    with pytest.raises(ImportAiError):
        provider.extract((DocumentPage(2, '', ''),))
    row = row_for(document())
    row.update(error_code='provider_unavailable', calls=provider.calls, result={})
    row['metrics'] = score_document(document(), row)
    metrics = aggregate([row])
    assert metrics['partial_document_errors'] == 1
    assert metrics['unexpected_document_errors'] == 1
    assert provider.calls[0]['usage'] == {'prompt_tokens': 10}
    assert provider.calls[1]['error_code'] == 'provider_unavailable'
    assert all(call['elapsed_seconds'] is None for call in provider.calls)


def test_live_measurement_records_duration_without_external_provider():
    provider = MeasuredProvider(ControlledProvider(document()), live=True)
    provider.extract((DocumentPage(1, '', ''),))
    assert provider.calls[0]['elapsed_seconds'] >= 0


def test_cost_requires_tariff_and_complete_usage():
    calls = [{'usage': {'prompt_tokens': 1_000, 'completion_tokens': 500}}]
    tariff = {'input_per_million': 2, 'output_per_million': 4, 'currency': 'USD', 'reference': 'fixture tariff'}
    assert cost_estimate(calls)['amount'] is None
    assert cost_estimate(calls + [{'usage': {}}], tariff)['amount'] is None
    assert cost_estimate(calls, tariff)['amount'] == 0.004


def test_review_cli_uses_saved_result_without_settings_or_requests(monkeypatch, tmp_path):
    report, template = evaluate(tmp_path)
    save_report(tmp_path, report, template)
    annotation = deepcopy(template)
    annotation['reviewer'] = 'Test annotation fixture'
    for claim in annotation['claims']:
        claim['grade'] = 'confirmed'
    for fact in annotation['facts']:
        fact['present'] = True
    path = tmp_path / 'review.json'
    path.write_text(json.dumps(annotation))

    def forbidden(*args, **kwargs):
        pytest.fail('Manual review must not call settings or provider')

    monkeypatch.setattr('app.infrastructure.config.settings.get_settings', forbidden)
    monkeypatch.setattr(httpx.Client, 'send', forbidden)
    monkeypatch.setattr('sys.argv', ['evaluate_import_ai.py', '--output', str(tmp_path), '--manual-review', str(path)])
    main()
    result = json.loads((tmp_path / 'results.json').read_text())
    assert result['manual']['status'] == 'complete'
    assert result['manual']['missing_required_facts'] == 0
    assert (tmp_path / 'manual-reviewed.md').exists()
    assert json.loads((tmp_path / 'manual-review-template.json').read_text())['reviewer'] is None
    with pytest.raises(ValueError):
        evaluate(tmp_path)


def test_live_output_cannot_overwrite_controlled_output_before_reading_settings(monkeypatch, tmp_path):
    report, review = evaluate(tmp_path)
    save_report(tmp_path, report, review)

    def forbidden():
        pytest.fail('Mode rejection must precede settings access')

    monkeypatch.setattr('app.infrastructure.config.settings.get_settings', forbidden)
    with pytest.raises(ValueError):
        evaluate(tmp_path, live=True)


@pytest.mark.parametrize('bad', ['-1', 'nan', 'inf'])
def test_cli_rejects_invalid_tariff_before_evaluation(monkeypatch, bad):
    monkeypatch.setattr(
        'sys.argv',
        [
            'evaluate_import_ai.py',
            '--input-cost-per-million',
            bad,
            '--output-cost-per-million',
            '1',
            '--currency',
            'USD',
            '--tariff-reference',
            'test',
        ],
    )
    with pytest.raises(SystemExit, match='2'):
        main()


def test_absent_summary_automatically_counts_guaranteed_fact_omissions():
    item = document('multipage-discharge.pdf')
    row = row_for(item)
    del row['result']['fields']['clinical_summary']
    counts = score_document(item, row)['counts']
    assert counts['missing_required_facts_without_summary'] == 3
    assert counts['format_errors'] == counts['page_errors'] == 0

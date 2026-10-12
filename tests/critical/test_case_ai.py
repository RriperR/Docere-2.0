"""Сводки: источники, личные результаты, отзыв доступа и надёжность доставки."""

import json
from dataclasses import replace
from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_clinical_cases import invite, setup_case
from test_import_ai import configure_ai, png_bytes
from test_records import _InMemoryStorage

from app.application.ports.import_jobs.ai import DocumentPage
from app.domain.case_ai import merge_summary_batches, SummaryExtraction, SummaryFact
from app.domain.import_ai import AiSource, ImportAiError
from app.infrastructure.adapters.case_ai.provider import parse_summary
from app.infrastructure.adapters.queue import case_ai
from app.infrastructure.adapters.repositories.medical_records.sqlalchemy_medical_record_repository import (
    SqlAlchemyMedicalRecordRepositoryAdapter,
)
from app.infrastructure.db.models._time import utc_now
from app.infrastructure.db.models.case_ai import CaseSummaryRunRow
from app.infrastructure.db.models.medical_records.medical_record import MedicalRecordRow
from app.infrastructure.db.models.medical_records.user_record_link import UserRecordLinkRow
from app.infrastructure.db.session import get_session_factory

pytestmark = pytest.mark.critical


def setup_summary(client, monkeypatch, *, bad=False):
    configure_ai(monkeypatch)
    view, records, ids, headers, patient = setup_case(client)
    storage = _InMemoryStorage()
    monkeypatch.setattr(case_ai, 'get_file_storage', lambda: storage)
    attachments = []
    with get_session_factory()() as session:
        repo = SqlAlchemyMedicalRecordRepositoryAdapter(session)
        for index, (name, mime, content) in enumerate(
            [
                ('scan.png', 'image/png', png_bytes()),
                *([('broken.pdf', 'application/pdf', b'%PDF-broken')] if bad else []),
            ]
        ):
            key = f'synthetic/{index}/{name}'
            storage.upload(key=key, content=content, content_type=mime)
            file = repo.add_attachment(
                UUID(records[0]['id']), None, ids[0], 'Doctor', 'document', name, key, mime, len(content)
            )
            attachments.append(file.id)
        session.commit()
    return view, records, ids, headers, patient, attachments


def start(client, view, headers, record_ids=None, key=None):
    payload = {
        'record_ids': record_ids or view['case']['record_ids'],
        'version': view['case']['version'],
        'idempotency_key': str(key or uuid4()),
        'consent': True,
    }
    response = client.post(f'/api/cases/{view["id"]}/ai-summary/runs', headers=headers, json=payload)
    return response, payload


class FakeProvider:
    """Управляемый провайдер не выполняет внешних вызовов."""

    def __init__(self, transport):
        self.transport = transport

    def extract(self, pages):
        return SummaryExtraction(
            (SummaryFact('Synthetic finding', 'fact', (AiSource(pages[0].number, 'Finding'),)),), (), date(2024, 8, 23)
        ), {'total_tokens': 3}


def test_summary_start_selection_consent_and_idempotency(record_client, monkeypatch):
    view, records, _, headers, _, _ = setup_summary(record_client, monkeypatch)
    url = f'/api/cases/{view["id"]}/ai-summary'
    assert record_client.get(url, headers=headers[0]).json() is None
    response, payload = start(record_client, view, headers[0])
    assert response.status_code == 202, response.text
    assert response.headers['cache-control'] == 'private, no-store'
    assert record_client.post(url + '/runs', headers=headers[0], json=payload).json()['id'] == response.json()['id']
    assert start(record_client, view, headers[0])[0].status_code == 409
    assert start(record_client, view, headers[0], [records[1]['id']])[0].status_code == 404
    assert record_client.post(url + '/runs', headers=headers[0], json={**payload, 'consent': False}).status_code == 422
    assert (
        record_client.post(
            url + '/runs', headers=headers[0], json={**payload, 'record_ids': [records[0]['id']] * 2}
        ).status_code
        == 422
    )
    assert start(record_client, view, headers[2])[0].status_code == 404
    assert 'storage_key' not in response.text and 'synthetic-test-token' not in response.text


def test_completed_summary_partial_success_and_private_results(record_client, monkeypatch):
    view, records, ids, headers, _, _ = setup_summary(record_client, monkeypatch, bad=True)
    monkeypatch.setattr(case_ai, 'ChatCompletionsCaseSummaryProvider', FakeProvider)
    view = invite(record_client, view, headers, ids[1])
    url = f'/api/cases/{view["id"]}'
    assert start(record_client, view, headers[1])[0].status_code == 403
    record_client.post(url + '/invitations/accept', headers=headers[1])
    version = record_client.get(url, headers=headers[0]).json()['case']['version']
    view['case']['version'] = version
    response, _ = start(record_client, view, headers[0])
    run = response.json()
    assert response.status_code == 202, response.text
    case_ai.process_case_summary(run['id'])
    result = record_client.get(url + '/ai-summary', headers=headers[0]).json()
    assert result['status'] == 'completed_with_errors'
    good, bad = result['documents']
    assert good['facts'][0]['sources'] == [{'page': 1, 'excerpt': 'Finding'}]
    assert good['checksum'] and good['page_count'] == 1
    assert bad['error_code'] == 'unreadable_document' and not bad['facts']
    assert record_client.get(url + '/ai-summary', headers=headers[1]).json() is None
    assert record_client.get(url + '/ai-summary/runs/' + run['id'], headers=headers[1]).status_code == 404
    record = record_client.get('/api/records/' + records[0]['id'], headers=headers[0]).json()
    assert record['status'] == 'unconfirmed'
    assert record['clinical_summary'] == records[0]['clinical_summary']
    case_ai.process_case_summary(run['id'])
    assert record_client.get(url + '/ai-summary', headers=headers[0]).json() == result


def test_cancel_and_lease_recovery_reject_late_answers(record_client, monkeypatch):
    view, _, _, headers, _, _ = setup_summary(record_client, monkeypatch)
    response, _ = start(record_client, view, headers[0])
    rid = UUID(response.json()['id'])
    old = uuid4()
    row, _ = case_ai.claim_summary(rid, old)
    assert not case_ai.claim_summary(rid, uuid4())
    document = case_ai.summary_to_domain(row).documents[0]
    with get_session_factory()() as session:
        session.get(CaseSummaryRunRow, rid).lease_expires_at = utc_now() - timedelta(seconds=1)
        session.commit()
    messages = []
    monkeypatch.setattr(case_ai.process_case_summary, 'apply_async', lambda **kw: messages.append(kw))
    assert case_ai.enqueue_case_summaries() == 1
    new = uuid4()
    assert case_ai.claim_summary(rid, new)
    assert not case_ai.save_summary_document(rid, old, replace(document, status='completed'))
    url = f'/api/cases/{view["id"]}/ai-summary/runs/{rid}/cancel'
    assert record_client.post(url, headers=headers[0]).json()['status'] == 'cancelled'
    assert not case_ai.save_summary_document(rid, new, replace(document, status='completed'))
    assert record_client.post(url, headers=headers[0]).json()['status'] == 'cancelled'


def test_revocation_hides_completed_result_and_cancels_running(record_client, monkeypatch):
    view, records, ids, headers, _, _ = setup_summary(record_client, monkeypatch)
    view = invite(record_client, view, headers, ids[1])
    url = f'/api/cases/{view["id"]}'
    record_client.post(url + '/invitations/accept', headers=headers[1])
    view = record_client.get(url, headers=headers[1]).json()
    response, _ = start(record_client, view, headers[1])
    rid, token = UUID(response.json()['id']), uuid4()
    row, _ = case_ai.claim_summary(rid, token)
    document = case_ai.summary_to_domain(row).documents[0]
    with get_session_factory()() as session:
        link = session.scalar(select(UserRecordLinkRow).where(UserRecordLinkRow.user_id == ids[1]))
        session.delete(link)
        session.commit()
    assert record_client.get(url + '/ai-summary', headers=headers[1]).status_code == 403
    assert not case_ai.summary_authorized(rid, token)
    assert not case_ai.save_summary_document(rid, token, replace(document, status='completed'))
    with get_session_factory()() as session:
        assert session.get(CaseSummaryRunRow, rid).status == 'cancelled'


def test_source_changes_invalidate_old_summary_and_redis_failure_is_recoverable(record_client, monkeypatch):
    view, records, _, headers, _, _ = setup_summary(record_client, monkeypatch)
    response, _ = start(record_client, view, headers[0])
    rid = UUID(response.json()['id'])

    def fail(**kwargs):
        raise ConnectionError('Redis unavailable')

    monkeypatch.setattr(case_ai.process_case_summary, 'apply_async', fail)
    assert case_ai.enqueue_case_summaries() == 0
    with get_session_factory()() as session:
        run = session.get(CaseSummaryRunRow, rid)
        assert run.status == 'queued' and run.delivery_attempts == 1
        run.next_delivery_at = utc_now() - timedelta(seconds=1)
        session.commit()
    sent = []
    monkeypatch.setattr(case_ai.process_case_summary, 'apply_async', lambda **kw: sent.append(kw))
    assert case_ai.enqueue_case_summaries() == 1
    with get_session_factory()() as session:
        record = session.get(MedicalRecordRow, UUID(records[0]['id']))
        record.updated_at = utc_now() + timedelta(seconds=1)
        session.commit()
    assert record_client.get(f'/api/cases/{view["id"]}/ai-summary', headers=headers[0]).status_code == 409
    assert case_ai.enqueue_case_summaries() == 0
    with get_session_factory()() as session:
        assert session.get(CaseSummaryRunRow, rid).status == 'cancelled'


@pytest.mark.parametrize(
    'change',
    [
        {'facts': [{'text': 'No source', 'category': 'fact', 'sources': []}]},
        {'facts': [{'text': 'Foreign page', 'category': 'fact', 'sources': [{'page': 2, 'excerpt': 'x'}]}]},
        {'event_date': '2026-02-30'},
        {'actions': ['publish']},
        {'multiple_patients': 'false'},
    ],
)
def test_summary_provider_rejects_invalid_json_and_sources(change):
    with pytest.raises(ImportAiError):
        parse_summary(json.dumps({'facts': [], **change}), (DocumentPage(1, 'Text', ''),))


def test_summary_ambiguity_across_batches_never_selects_arbitrary_date():
    first = SummaryExtraction((), (), date(2024, 8, 23))
    second = SummaryExtraction((), (), date(2025, 4, 17))
    result = merge_summary_batches([first, second])
    assert result.event_date is None and 'conflicting:event_date' in result.issues
    parsed = parse_summary(
        json.dumps({'facts': [], 'event_date': '2024-08-23', 'ambiguous_date': True}), (DocumentPage(1, '', ''),)
    )
    assert parsed.event_date is None


def test_concurrent_start_and_global_ai_limit(postgres_case_client, monkeypatch):
    """PostgreSQL сериализует одинаковый старт и общий лимит с импортом."""
    from concurrent.futures import ThreadPoolExecutor

    from test_import_ai import start as start_import
    from test_import_ai import upload_job

    from app.infrastructure.adapters.queue import import_ai
    from app.infrastructure.config.settings import clear_settings_cache

    client = postgres_case_client
    view, _, _, headers, _, _ = setup_summary(client, monkeypatch)
    monkeypatch.setenv('APP_IMPORT_AI__CONCURRENCY', '1')
    clear_settings_cache()
    payload = {
        'record_ids': view['case']['record_ids'],
        'version': view['case']['version'],
        'idempotency_key': str(uuid4()),
        'consent': True,
    }
    url = f'/api/cases/{view["id"]}/ai-summary/runs'
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post(url, headers=headers[0], json=payload), range(2)))
    assert all(r.status_code == 202 for r in responses), [r.text for r in responses]
    rid = UUID(responses[0].json()['id'])
    assert responses[1].json()['id'] == str(rid)
    assert case_ai.claim_summary(rid, uuid4())
    jid, import_headers, job = upload_job(client, monkeypatch)
    response, _ = start_import(client, jid, import_headers, job)
    assert response.status_code == 202, response.text
    imported = UUID(response.json()['id'])
    assert import_ai.claim_ai_run(imported, uuid4()) is None
    assert client.post(url + f'/{rid}/cancel', headers=headers[0]).status_code == 200
    assert import_ai.claim_ai_run(imported, uuid4())
    second, _ = start(client, view, headers[0])
    assert second.status_code == 202
    assert case_ai.claim_summary(UUID(second.json()['id']), uuid4()) is None


def test_multiple_patient_document_fails_without_exposing_facts(record_client, monkeypatch):
    view, _, _, headers, _, _ = setup_summary(record_client, monkeypatch)

    class ConflictingProvider(FakeProvider):
        def extract(self, pages):
            result, usage = super().extract(pages)
            return replace(result, multiple_patients=True), usage

    monkeypatch.setattr(case_ai, 'ChatCompletionsCaseSummaryProvider', ConflictingProvider)
    response, _ = start(record_client, view, headers[0])
    case_ai.process_case_summary(response.json()['id'])
    result = record_client.get(f'/api/cases/{view["id"]}/ai-summary', headers=headers[0]).json()
    assert result['status'] == 'failed'
    assert result['documents'][0]['error_code'] == 'multiple_patients_document'
    assert result['documents'][0]['facts'] == []


def test_different_patients_in_separate_page_batches_are_not_combined():
    first = SummaryExtraction((), (), patient_name='Synthetic One', patient_birth_date=date(1980, 1, 1))
    second = SummaryExtraction((), (), patient_name='Synthetic Two', patient_birth_date=date(1980, 1, 1))
    assert merge_summary_batches([first, second]).multiple_patients
    assert merge_summary_batches([first, replace(first, patient_birth_date=date(1990, 1, 1))]).multiple_patients
    assert not merge_summary_batches([first, replace(first, patient_name='  SYNTHETIC   ONE ')]).multiple_patients


def test_repeated_fact_keeps_all_source_pages_without_duplicate_bullets():
    first = SummaryFact('Synthetic finding', 'fact', (AiSource(1, 'Finding'),))
    second = SummaryFact('  SYNTHETIC   finding ', 'fact', (AiSource(2, 'Finding'),))
    result = merge_summary_batches([SummaryExtraction((first,), ()), SummaryExtraction((second,), ())])
    assert len(result.facts) == 1
    assert result.facts[0].sources == (AiSource(1, 'Finding'), AiSource(2, 'Finding'))

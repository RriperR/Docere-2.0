"""AI-импорт: внешний контракт, ограничения и ручная проверка."""

import json
from io import BytesIO
from uuid import UUID, uuid4

import httpx
import pytest
from PIL import Image
from sqlalchemy import select
from test_records import _create_doctor, _InMemoryStorage, _login, TEST_DOCTOR_PASSWORD

from app.application.ports.import_jobs.ai import DocumentPage
from app.domain.import_ai import AiExtraction, AiField, AiSource, ImportAiError, merge_extractions
from app.infrastructure.adapters.import_jobs.ai_provider import ChatCompletionsImportProvider, parse_extraction
from app.infrastructure.adapters.import_jobs.document_pages import DocumentPages
from app.infrastructure.adapters.queue import import_ai
from app.infrastructure.adapters.queue.tasks import process_import_job
from app.infrastructure.config.settings import clear_settings_cache
from app.infrastructure.db.models.import_ai import ImportAiRunRow
from app.infrastructure.db.session import get_session_factory

pytestmark = pytest.mark.critical


def png_bytes():
    output = BytesIO()
    with Image.new('RGB', (40, 40), 'white') as image:
        image.save(output, format='PNG')
    return output.getvalue()


def facts(page=1):
    return {
        'fields': {
            'title': {'value': 'Результат обследования', 'sources': [{'page': page, 'excerpt': 'Обследование'}]},
            'event_date': {'value': '2026-10-11', 'sources': [{'page': page, 'excerpt': '11.10.2026'}]},
            'clinical_summary': {
                'value': 'Указано выполненное обследование.',
                'sources': [{'page': page, 'excerpt': 'Обследование выполнено'}],
            },
        },
        'issues': [],
        'multiple_patients': False,
    }


def configure_ai(monkeypatch):
    monkeypatch.setenv('APP_IMPORT_AI__ENABLED', 'true')
    monkeypatch.setenv('APP_IMPORT_AI__MODEL', 'synthetic-vision')
    monkeypatch.setenv('APP_IMPORT_AI__BASE_URL', 'https://provider.example/v1')
    monkeypatch.setenv('APP_IMPORT_AI__TOKEN', 'synthetic-test-token')
    clear_settings_cache()


def upload_job(client, monkeypatch, files=None, automatic=False):
    storage = _InMemoryStorage()
    for target in [
        'app.presentation.rest.public.v1.archives.router.get_file_storage',
        'app.infrastructure.adapters.queue.tasks.get_file_storage',
        'app.infrastructure.adapters.queue.import_ai.get_file_storage',
    ]:
        monkeypatch.setattr(target, lambda: storage)
    _create_doctor(email='ai-owner@example.com')
    token = _login(client, 'ai-owner@example.com', TEST_DOCTOR_PASSWORD)
    headers = {'Authorization': 'Bearer ' + token}
    response = client.post(
        '/api/archives/imports',
        headers=headers,
        data={'ai_requested': str(automatic).lower()},
        files=files or [('files', ('scan.png', png_bytes(), 'image/png'))],
    )
    assert response.status_code == 201
    jid = response.json()['id']
    process_import_job(jid)
    job = client.get('/api/archives/imports/' + jid, headers=headers).json()
    return jid, headers, job


def start(client, jid, headers, job, key=None):
    file_ids = [f['id'] for p in job['report_json']['patients'] for g in p['record_groups'] for f in g['files']]
    payload = {'file_ids': file_ids, 'version': job['version'], 'idempotency_key': str(key or uuid4())}
    response = client.post(f'/api/archives/imports/{jid}/ai-runs', headers=headers, json=payload)
    return response, payload


def test_provider_contract_retries_and_validates_sources():
    seen = []

    def handle(request):
        seen.append(json.loads(request.content))
        if len(seen) == 1:
            return httpx.Response(429)
        return httpx.Response(
            200,
            json={
                'choices': [{'message': {'content': json.dumps(facts())}, 'finish_reason': 'stop'}],
                'usage': {'total_tokens': 12},
            },
        )

    provider = ChatCompletionsImportProvider(
        'https://provider.example/v1', 'vision', 'test-only', transport=httpx.MockTransport(handle), wait=lambda _: None
    )
    result, usage = provider.extract((DocumentPage(1, 'Обследование выполнено', 'encoded-image'),))
    assert result.fields['title'].value == 'Результат обследования'
    assert usage == {'total_tokens': 12}
    assert seen[0]['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,')
    assert 'tools' not in seen[0]
    with pytest.raises(ImportAiError, match='invalid_response'):
        parse_extraction(json.dumps(facts(page=2)), (DocumentPage(1, '', ''),))
    invalid = facts()
    invalid['fields']['event_date']['value'] = '2026-02-31'
    with pytest.raises(ImportAiError, match='invalid_response'):
        parse_extraction(json.dumps(invalid), (DocumentPage(1, '', ''),))


def test_conflicting_patient_facts_are_not_merged():
    one = AiExtraction({'fio': AiField('Иванов Иван', (AiSource(1, 'Иванов Иван'),))})
    two = AiExtraction({'fio': AiField('Петров Пётр', (AiSource(2, 'Петров Пётр'),))})
    result = merge_extractions([one, two])
    assert 'fio' not in result['fields']
    assert result['patient_conflict'] is True
    assert 'conflicting:fio' in result['issues']


def test_images_and_unreadable_documents():
    pages = DocumentPages().prepare(png_bytes(), 'image/png', 30)
    assert len(pages) == 1 and pages[0].image_base64
    with pytest.raises(ImportAiError, match='unreadable_document'):
        DocumentPages().prepare(b'%PDF-broken', 'application/pdf', 30)
    with pytest.raises(ImportAiError, match='unsupported_document'):
        DocumentPages().prepare(b'DICOM', 'application/dicom', 30)


def test_ai_run_idempotency_worker_result_and_access(record_client, monkeypatch):
    configure_ai(monkeypatch)
    jid, headers, job = upload_job(record_client, monkeypatch)
    capabilities = record_client.get('/api/archives/ai-capabilities', headers=headers)
    assert capabilities.json()['enabled'] is True
    assert 'token' not in capabilities.text and 'base_url' not in capabilities.text
    created, payload = start(record_client, jid, headers, job)
    assert created.status_code == 202
    run_id = created.json()['id']
    repeated = record_client.post(f'/api/archives/imports/{jid}/ai-runs', headers=headers, json=payload)
    assert repeated.json()['id'] == run_id
    second, _ = start(record_client, jid, headers, job)
    assert second.status_code == 409
    actual_class = ChatCompletionsImportProvider
    monkeypatch.setattr(
        import_ai,
        'ChatCompletionsImportProvider',
        lambda *a, **kw: actual_class(
            *a,
            **kw,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200, json={'choices': [{'message': {'content': json.dumps(facts())}, 'finish_reason': 'stop'}]}
                )
            ),
        ),
    )
    import_ai.process_import_ai(run_id)
    url = f'/api/archives/imports/{jid}/ai-runs/{run_id}'
    result = record_client.get(url, headers=headers).json()
    assert result['status'] == 'completed'
    assert result['documents'][0]['page_count'] == 1
    assert len(result['documents'][0]['checksum']) == 64
    assert result['documents'][0]['result']['fields']['title']['sources'][0]['page'] == 1
    import_ai.process_import_ai(run_id)
    assert record_client.get(url, headers=headers).json() == result
    _create_doctor(email='ai-outsider@example.com')
    other_token = _login(record_client, 'ai-outsider@example.com', TEST_DOCTOR_PASSWORD)
    assert record_client.get(url, headers={'Authorization': 'Bearer ' + other_token}).status_code == 404
    assert record_client.get('/api/archives/imports/' + jid, headers=headers).json()['review_decisions'] == []


def test_cancel_rejects_late_document_and_automatic_uses_same_run(record_client, monkeypatch):
    configure_ai(monkeypatch)
    jid, headers, job = upload_job(record_client, monkeypatch, automatic=True)
    import_ai.start_automatic_import_ai(UUID(jid))
    import_ai.start_automatic_import_ai(UUID(jid))
    with get_session_factory()() as session:
        rows = session.scalars(select(ImportAiRunRow).where(ImportAiRunRow.job_id == UUID(jid))).all()
        assert len(rows) == 1
        run_id = rows[0].id
    token = uuid4()
    claim = import_ai.claim_ai_run(run_id, token)
    assert claim is not None
    response = record_client.post(f'/api/archives/imports/{jid}/ai-runs/{run_id}/cancel', headers=headers)
    assert response.json()['status'] == 'cancelled'
    assert not import_ai.ai_authorized(run_id, token)
    assert not import_ai.save_ai_document(run_id, token, claim.run.documents[0].file_id, {'fields': {}}, 1, None, {})

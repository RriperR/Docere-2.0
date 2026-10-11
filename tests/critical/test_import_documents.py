"""Отдельные документы, доступ к исходникам и конфликт черновиков."""

import pytest
from test_records import _create_doctor, _InMemoryStorage, _login, TEST_DOCTOR_PASSWORD

from app.application.ports.import_jobs.document_bundle import UploadedDocument
from app.application.use_cases.import_jobs.errors import ImportJobValidationError
from app.infrastructure.adapters.import_jobs.document_bundle import DocumentBundle
from app.infrastructure.adapters.queue.tasks import process_import_job

pytestmark = pytest.mark.critical


def test_document_bundle_rejects_disguised_file():
    with pytest.raises(ImportJobValidationError):
        DocumentBundle().pack((UploadedDocument('report.pdf', b'not a PDF'),))


def test_documents_preview_review_version_and_description(record_client, monkeypatch):
    storage = _InMemoryStorage()
    monkeypatch.setattr('app.presentation.rest.public.v1.archives.router.get_file_storage', lambda: storage)
    monkeypatch.setattr('app.infrastructure.adapters.queue.tasks.get_file_storage', lambda: storage)
    _create_doctor(email='documents@example.com')
    token = _login(record_client, 'documents@example.com', TEST_DOCTOR_PASSWORD)
    headers = {'Authorization': f'Bearer {token}'}
    uploaded = record_client.post(
        '/api/archives/imports',
        headers=headers,
        files=[
            ('files', ('report.pdf', b'%PDF-1.4 first', 'application/pdf')),
            ('files', ('report.pdf', b'%PDF-1.4 second', 'application/pdf')),
        ],
    )
    assert uploaded.status_code == 201
    job_id = uploaded.json()['id']
    process_import_job(job_id)
    job = record_client.get(f'/api/archives/imports/{job_id}', headers=headers).json()
    patient = job['report_json']['patients'][0]
    groups = patient['record_groups']
    assert len(groups) == 2
    assert groups[0]['files'][0]['id'] != groups[1]['files'][0]['id']
    url = f'/api/archives/imports/{job_id}/files/{groups[0]["files"][0]["id"]}'
    source = record_client.get(url, headers=headers)
    assert source.content == b'%PDF-1.4 first'
    assert source.headers['cache-control'] == 'no-store'
    _create_doctor(email='other-documents@example.com')
    other_token = _login(record_client, 'other-documents@example.com', TEST_DOCTOR_PASSWORD)
    assert record_client.get(url, headers={'Authorization': f'Bearer {other_token}'}).status_code == 404
    decisions = [
        {
            'candidate_id': patient['candidate_id'],
            'action': 'create',
            'fio': 'Тестовый пациент',
            'record_groups': [
                {
                    'group_id': g['group_id'],
                    'action': 'create',
                    'event_date': '2026-10-11',
                    'clinical_summary': 'Проверено врачом',
                }
                for g in groups
            ],
        }
    ]
    draft = {'version': job['version'], 'decisions': decisions}
    saved = record_client.put(f'/api/archives/imports/{job_id}/review-draft', headers=headers, json=draft)
    assert saved.status_code == 200
    assert (
        record_client.put(f'/api/archives/imports/{job_id}/review-draft', headers=headers, json=draft).status_code
        == 409
    )
    response = record_client.post(
        f'/api/archives/imports/{job_id}/resolve',
        headers=headers,
        json={'version': saved.json()['version'], 'decisions': decisions},
    )
    assert response.status_code == 200
    ids = response.json()['report_json']['resolved_patients'][0]['record_ids']
    record = record_client.get(f'/api/records/{ids[0]}', headers=headers).json()
    assert record['clinical_summary'] == 'Проверено врачом'
    assert record['status'] == 'unconfirmed'

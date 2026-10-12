"""Mixed ZIP E1: DICOM не попадает ни в ручной, ни в автоматический AI-анализ."""

import runpy
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select
from test_import_ai import configure_ai, upload_job

from app.domain.import_ai import AiExtraction
from app.infrastructure.adapters.queue import import_ai
from app.infrastructure.db.models.import_ai import ImportAiRunRow
from app.infrastructure.db.session import get_session_factory

pytestmark = pytest.mark.critical


def test_mixed_zip_excludes_dicom_before_provider(record_client, monkeypatch):
    dataset = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'scripts/import_ai_dataset.py'))
    manifest = dataset['load_manifest']()
    configure_ai(monkeypatch)
    calls = []

    class ControlledProvider:
        def __init__(self, *args, **kwargs):
            pass

        def extract(self, pages):
            calls.append(pages)
            return AiExtraction({}), {}

    def unexpected_network(*args, **kwargs):
        pytest.fail('E1 gate не должен делать внешние AI-запросы')

    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', unexpected_network)
    monkeypatch.setattr(import_ai, 'ChatCompletionsImportProvider', ControlledProvider)
    jid, headers, job = upload_job(
        record_client,
        monkeypatch,
        files=[('file', (manifest['mixed_zip']['name'], dataset['make_mixed_zip'](), 'application/zip'))],
        automatic=True,
    )
    files = [f for p in job['report_json']['patients'] for g in p['record_groups'] for f in g['files']]
    assert len(files) == 3
    dicom = [f for f in files if f['is_dicom']]
    assert len(dicom) == 1 and dicom[0]['mime_type'] == 'application/dicom'
    rejected = record_client.post(
        f'/api/archives/imports/{jid}/ai-runs',
        headers=headers,
        json={'file_ids': [f['id'] for f in files], 'version': job['version'], 'idempotency_key': str(uuid4())},
    )
    assert rejected.status_code == 422
    assert not calls
    import_ai.start_automatic_import_ai(UUID(jid))
    with get_session_factory()() as session:
        runs = session.scalars(select(ImportAiRunRow).where(ImportAiRunRow.job_id == UUID(jid))).all()
        assert len(runs) == 1
        run_id = str(runs[0].id)
    import_ai.process_import_ai(run_id)
    result = record_client.get(f'/api/archives/imports/{jid}/ai-runs/{run_id}', headers=headers).json()
    assert result['status'] == 'completed'
    assert {d['file_id'] for d in result['documents']} == {f['id'] for f in files if not f['is_dicom']}
    assert len(calls) == len(manifest['mixed_zip']['expected_ai_documents']) == 2
    assert all(len(pages) == 1 and pages[0].image_base64 for pages in calls)
    assert all('Synthetic^Dicom' not in page.text for pages in calls for page in pages)

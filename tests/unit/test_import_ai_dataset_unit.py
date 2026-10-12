"""Эталон E1: источники, воспроизводимость и локальная подготовка без AI."""

import json
import runpy
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image

from app.application.use_cases.import_jobs.ai import AnalyzeImportDocumentUseCase
from app.domain.import_ai import AiOptions, ImportAiError
from app.infrastructure.adapters.import_jobs.document_pages import DocumentPages

ROOT = Path(__file__).resolve().parents[2]
DATASET = runpy.run_path(str(ROOT / 'scripts/import_ai_dataset.py'))
MANIFEST = DATASET['load_manifest']()
DOCUMENTS = MANIFEST['documents']


def test_manifest_coverage_and_frozen_splits():
    assert MANIFEST['synthetic_only'] is True
    assert len(DOCUMENTS) >= 20
    assert len({d['name'] for d in DOCUMENTS}) == len(DOCUMENTS)
    assert {d['split'] for d in DOCUMENTS} == {'development', 'holdout'}
    tags = {tag for d in DOCUMENTS for tag in d['tags']}
    assert {
        'text_pdf',
        'scan',
        'photo',
        'rotated',
        'low_quality',
        'batch_boundary',
        'multiple_packets',
        'missing_date',
        'ambiguous_date',
        'birth_near_event',
        'multiple_patients',
        'different_patient',
        'contradiction',
        'injection',
        'protected',
        'unreadable',
    } <= tags
    assert len([d for d in DOCUMENTS if d['split'] == 'holdout']) == 9
    assert max(len(d['pages']) for d in DOCUMENTS) > AiOptions().batch_pages
    for split in ('development', 'holdout'):
        split_tags = {tag for d in DOCUMENTS if d['split'] == split for tag in d['tags']}
        assert {'missing_date', 'ambiguous_date', 'multiple_patients', 'injection'} <= split_tags


@pytest.mark.parametrize('document', DOCUMENTS, ids=lambda d: d['name'])
def test_expected_sources_belong_to_document(document):
    pages = {p['number']: p['text'] for p in document['pages']}
    assert list(pages) == list(range(1, len(pages) + 1))
    expected = document['expected']
    assert not set(expected['empty_fields']) & set(expected['fields'])
    for field in expected['fields'].values():
        assert field['allowed_values'] and field['sources']
    for item in [*expected['fields'].values(), *expected['facts']]:
        assert item['sources']
        for source in item['sources']:
            assert source['excerpt'] in pages[source['page']]
    if expected['error_code']:
        assert set(expected['empty_fields']) == {
            'fio',
            'date_of_birth',
            'event_date',
            'record_type',
            'title',
            'clinical_summary',
        }
    else:
        assert expected['facts']


@pytest.mark.parametrize('document', DOCUMENTS, ids=lambda d: d['name'])
def test_generated_documents_prepare_with_expected_page_count(document):
    content, mime = DATASET['make_document'](document)
    if document['expected']['error_code']:
        with pytest.raises(ImportAiError, match=document['expected']['error_code']):
            DocumentPages().prepare(content, mime, 30)
        return
    pages = DocumentPages().prepare(content, mime, 30)
    assert [p.number for p in pages] == [p['number'] for p in document['pages']]
    assert all(p.image_base64 for p in pages)
    if document['render'] == 'text_pdf':
        for actual, source in zip(pages, document['pages'], strict=True):
            assert ' '.join(source['text'].split()) == ' '.join(actual.text.split())
    else:
        assert all(not page.text for page in pages)
    if document.get('rotation'):
        with Image.open(BytesIO(content)) as image:
            assert image.height > image.width


def test_generator_is_repeatable_and_manifest_matches_written_files(tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    DATASET['generate'](first)
    generated = DATASET['generate'](second)
    assert sorted(p.name for p in first.iterdir()) == sorted(p.name for p in second.iterdir())
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    assert generated == json.loads((second / 'manifest.json').read_text())
    for document in generated['documents']:
        assert sha256((second / document['name']).read_bytes()).hexdigest() == document['sha256']
    with ZipFile(second / MANIFEST['mixed_zip']['name']) as archive:
        assert len(archive.namelist()) == 3
        assert archive.read(MANIFEST['mixed_zip']['dicom'])[128:132] == b'DICM'


def test_split_generation_does_not_include_holdout_documents(tmp_path):
    generated = DATASET['generate'](tmp_path, 'development')
    assert generated['selected_split'] == 'development'
    assert all(d['split'] == 'development' for d in generated['documents'])
    assert all(not (tmp_path / d['name']).exists() for d in DOCUMENTS if d['split'] == 'holdout')


def test_holdout_generation_does_not_include_development_documents(tmp_path):
    generated = DATASET['generate'](tmp_path, 'holdout')
    assert generated['selected_split'] == 'holdout'
    assert len(generated['documents']) == 9
    assert all(not (tmp_path / d['name']).exists() for d in DOCUMENTS if d['split'] == 'development')
    assert not (tmp_path / MANIFEST['mixed_zip']['name']).exists()
    assert 'mixed_zip' not in generated
    assert 'mixed_zip' not in json.loads((tmp_path / 'manifest.json').read_text())


@pytest.mark.parametrize(
    ('previous_split', 'next_split'),
    [
        ('all', 'holdout'),
        ('all', 'development'),
        ('development', 'holdout'),
        ('development', 'all'),
        ('holdout', 'development'),
        ('holdout', 'all'),
    ],
)
def test_split_transition_rejected_before_writes_without_deleting_files(tmp_path, previous_split, next_split):
    DATASET['generate'](tmp_path, previous_split)
    (tmp_path / 'personal-notes.txt').write_text('Keep this file')
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(ValueError, match='another dataset version or split'):
        DATASET['generate'](tmp_path, next_split)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


@pytest.mark.parametrize('split', ['all', 'development', 'holdout'])
def test_same_split_can_be_regenerated_preserving_unrelated_files(tmp_path, split):
    first = DATASET['generate'](tmp_path, split)
    (tmp_path / 'personal-notes.txt').write_text('Keep this file')
    assert DATASET['generate'](tmp_path, split) == first
    assert (tmp_path / 'personal-notes.txt').read_text() == 'Keep this file'


def test_unmanaged_nonempty_output_is_rejected_without_writes(tmp_path):
    (tmp_path / 'personal-notes.txt').write_text('Keep this file')
    with pytest.raises(ValueError, match='not a managed dataset directory'):
        DATASET['generate'](tmp_path, 'holdout')
    assert [p.name for p in tmp_path.iterdir()] == ['personal-notes.txt']


def test_incompatible_stale_documents_are_rejected_even_with_matching_manifest(tmp_path):
    DATASET['generate'](tmp_path, 'holdout')
    (tmp_path / 'text-report.pdf').write_bytes(b'Stale development document')
    with pytest.raises(ValueError, match='outside the selected split'):
        DATASET['generate'](tmp_path, 'holdout')
    assert (tmp_path / 'text-report.pdf').read_bytes() == b'Stale development document'


def test_default_cli_outputs_keep_splits_separate(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for split in ('all', 'holdout', 'development'):
        monkeypatch.setattr('sys.argv', ['import_ai_dataset.py', '--split', split])
        runpy.run_path(str(ROOT / 'scripts/import_ai_dataset.py'), run_name='__main__')
    assert len(json.loads((tmp_path / 'artifacts/import-ai-dataset/manifest.json').read_text())['documents']) == 24
    holdout = json.loads((tmp_path / 'artifacts/import-ai-dataset-holdout/manifest.json').read_text())
    assert len(holdout['documents']) == 9 and 'mixed_zip' not in holdout
    development = json.loads((tmp_path / 'artifacts/import-ai-dataset-development/manifest.json').read_text())
    assert len(development['documents']) == 15


def test_legacy_five_samples_are_preserved(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    legacy = runpy.run_path(str(ROOT / 'scripts/evaluate_import_ai.py'))
    names = [
        'multipage-discharge.pdf',
        'blurred-photo.jpg',
        'several-dates.png',
        'no-date.png',
        'document-instructions.png',
    ]
    assert [sample.name for sample in legacy['SAMPLES']] == names
    expected = {d['name']: d for d in DOCUMENTS if 'legacy' in d['tags']}
    for sample in legacy['SAMPLES']:
        document = expected[sample.name]
        assert sample.pages == tuple(p['text'] for p in document['pages'])
        values = document['expected']['fields'].get('event_date', {}).get('allowed_values', [None])
        assert sample.event_date == values[0]
        assert legacy['make_document'](sample) == DATASET['make_document'](document)


@pytest.mark.parametrize('name', ['protected-document.pdf', 'corrupt-document.pdf'])
def test_unreadable_documents_never_reach_provider(name):
    class UnexpectedProvider:
        def extract(self, pages):
            pytest.fail('Нечитаемый документ нельзя отправлять провайдеру')

    document = next(d for d in DOCUMENTS if d['name'] == name)
    content, mime = DATASET['make_document'](document)
    analyze = AnalyzeImportDocumentUseCase(DocumentPages(), UnexpectedProvider(), AiOptions())
    with pytest.raises(ImportAiError, match='unreadable_document'):
        analyze.analyze(content, mime, 30, lambda: True)


def test_default_evaluation_generates_without_reading_provider_settings(monkeypatch, tmp_path):
    from app.infrastructure.config import settings

    def unexpected_settings():
        pytest.fail('Генерация не должна читать настройки или секреты провайдера')

    monkeypatch.setattr(settings, 'get_settings', unexpected_settings)
    monkeypatch.syspath_prepend(str(ROOT))
    monkeypatch.setattr('sys.argv', ['evaluate_import_ai.py', '--output', str(tmp_path)])
    runpy.run_path(str(ROOT / 'scripts/evaluate_import_ai.py'), run_name='__main__')
    assert len(json.loads((tmp_path / 'manifest.json').read_text())['documents']) == 24

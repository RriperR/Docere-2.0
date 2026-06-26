from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid, SecondaryCaptureImageStorage

from app.application.use_cases.import_jobs import extractor
from app.application.use_cases.import_jobs.extractor import ArchiveExtractionError, extract_import_draft


def _zip_bytes(entries: dict[str, bytes], *, compression: int | None = None) -> bytes:
    buffer = BytesIO()
    kwargs = {'compression': compression} if compression is not None else {}
    with ZipFile(buffer, mode='w', **kwargs) as archive:
        for path, content in entries.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _dicom_bytes(
    *,
    patient_name: str = 'Petrov^Petr^Petrovich',
    patient_birth_date: str = '19750506',
    study_date: str = '20260407',
    study_uid: str | None = None,
    series_uid: str | None = None,
) -> bytes:
    buffer = BytesIO()
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = generate_uid()
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    dataset = FileDataset('study.dcm', {}, file_meta=file_meta, preamble=b'\0' * 128)
    dataset.PatientName = patient_name
    dataset.PatientBirthDate = patient_birth_date
    dataset.StudyDate = study_date
    dataset.Modality = 'MR'
    dataset.StudyDescription = 'Brain MRI'
    dataset.SeriesDescription = 'T2'
    dataset.StudyInstanceUID = study_uid or generate_uid()
    dataset.SeriesInstanceUID = series_uid or generate_uid()
    dataset.save_as(buffer, enforce_file_format=True)
    return buffer.getvalue()


@pytest.mark.critical
def test_extract_import_draft_parses_regular_zip_with_explicit_birth_date() -> None:
    report = extract_import_draft(
        archive_filename='records.zip',
        archive_content=_zip_bytes(
            {
                'Иванов Иван Иванович/dob 1980-01-02/lab 2026-04-05/result.pdf': b'%PDF-1.4',
            },
        ),
    )

    patient = report['patients'][0]
    record_group = patient['record_groups'][0]
    assert patient['fio'] == 'Иванов Иван Иванович'
    assert patient['date_of_birth'] == '1980-01-02'
    assert record_group['event_date'] == '2026-04-05'
    assert record_group['record_type'] == 'lab_result'
    assert report['files_total'] == 1


@pytest.mark.critical
def test_extract_import_draft_does_not_use_unmarked_path_date_as_birth_date() -> None:
    report = extract_import_draft(
        archive_filename='records.zip',
        archive_content=_zip_bytes(
            {
                'Иванов Иван Иванович 1980-01-02/lab/result.pdf': b'%PDF-1.4',
            },
        ),
    )

    patient = report['patients'][0]
    assert patient['fio'] == 'Иванов Иван Иванович'
    assert patient['date_of_birth'] is None


@pytest.mark.critical
def test_extract_import_draft_offers_multiple_unmarked_dates_for_review() -> None:
    report = extract_import_draft(
        archive_filename='records.zip',
        archive_content=_zip_bytes(
            {
                'Иванов Иван Иванович/lab 2026-04-05 repeat 2026-04-06/result.pdf': b'%PDF-1.4',
            },
        ),
    )

    record_group = report['patients'][0]['record_groups'][0]
    assert record_group['event_date'] is None
    assert record_group['event_date_candidates'] == ['2026-04-05', '2026-04-06']
    assert any('Multiple date candidates' in warning for warning in report['warnings'])


@pytest.mark.critical
def test_extract_import_draft_parses_dicom_patient_and_study_metadata() -> None:
    study_uid = generate_uid()
    report = extract_import_draft(
        archive_filename='dicom.zip',
        archive_content=_zip_bytes(
            {
                'dicom/study.dcm': _dicom_bytes(study_uid=study_uid),
            },
        ),
    )

    patient = report['patients'][0]
    record_group = patient['record_groups'][0]
    dicom_metadata = record_group['payload_json']['dicom_metadata'][0]
    assert patient['fio'] == 'Petrov Petr Petrovich'
    assert patient['date_of_birth'] == '1975-05-06'
    assert record_group['event_date'] == '2026-04-07'
    assert record_group['record_type'] == 'exam_result'
    assert dicom_metadata['StudyInstanceUID'] == study_uid
    assert dicom_metadata['Modality'] == 'MR'


@pytest.mark.critical
def test_extract_import_draft_groups_dicom_by_study_uid_before_series_uid() -> None:
    study_uid = generate_uid()
    report = extract_import_draft(
        archive_filename='dicom.zip',
        archive_content=_zip_bytes(
            {
                'dicom/series-a/image.dcm': _dicom_bytes(study_uid=study_uid, series_uid=generate_uid()),
                'dicom/series-b/image.dcm': _dicom_bytes(study_uid=study_uid, series_uid=generate_uid()),
            },
        ),
    )

    assert len(report['patients'][0]['record_groups']) == 1
    assert len(report['patients'][0]['record_groups'][0]['files']) == 2


@pytest.mark.critical
def test_extract_import_draft_rejects_corrupted_zip() -> None:
    with pytest.raises(ArchiveExtractionError, match='valid ZIP'):
        extract_import_draft(archive_filename='bad.zip', archive_content=b'not a zip')


@pytest.mark.critical
def test_extract_import_draft_skips_unsafe_system_and_empty_files() -> None:
    report = extract_import_draft(
        archive_filename='records.zip',
        archive_content=_zip_bytes(
            {
                '../evil.txt': b'evil',
                '/absolute/path.txt': b'absolute',
                'C:/Windows/file.txt': b'windows',
                '__MACOSX/file.txt': b'macos',
                '.DS_Store': b'ds',
                'empty.txt': b'',
                'valid/lab 2026-04-05/result.txt': b'ok',
            },
        ),
    )

    record_group = report['patients'][0]['record_groups'][0]
    assert report['files_total'] == 1
    assert record_group['files'][0]['path'] == 'valid/lab 2026-04-05/result.txt'
    assert len(report['warnings']) == 6
    assert any('../evil.txt' in warning for warning in report['warnings'])
    assert any('/absolute/path.txt' in warning for warning in report['warnings'])
    assert any('C:/Windows/file.txt' in warning for warning in report['warnings'])
    assert any('__MACOSX/file.txt' in warning for warning in report['warnings'])
    assert any('.DS_Store' in warning for warning in report['warnings'])
    assert any('empty.txt' in warning for warning in report['warnings'])


@pytest.mark.critical
def test_extract_import_draft_applies_zip_file_count_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extractor, '_MAX_ZIP_FILES', 1)

    report = extract_import_draft(
        archive_filename='records.zip',
        archive_content=_zip_bytes(
            {
                'valid/one.txt': b'ok',
                'valid/two.txt': b'ok',
            },
        ),
    )

    assert report['files_total'] == 1
    assert any('file count limit' in warning for warning in report['warnings'])


@pytest.mark.critical
def test_extract_import_draft_applies_zip_size_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extractor, '_MAX_ZIP_FILE_SIZE_BYTES', 4)
    monkeypatch.setattr(extractor, '_MAX_ZIP_TOTAL_UNCOMPRESSED_SIZE_BYTES', 6)

    report = extract_import_draft(
        archive_filename='records.zip',
        archive_content=_zip_bytes(
            {
                'valid/one.txt': b'ok',
                'valid/large.txt': b'too large',
                'valid/two.txt': b'ok',
                'valid/three.txt': b'ok',
                'valid/four.txt': b'ok',
            },
        ),
    )

    assert report['files_total'] == 3
    assert any('file over size limit' in warning for warning in report['warnings'])
    assert any('total uncompressed size limit' in warning for warning in report['warnings'])


@pytest.mark.critical
def test_extract_import_draft_applies_zip_compression_ratio_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(extractor, '_MAX_ZIP_FILE_SIZE_BYTES', 2000)
    monkeypatch.setattr(extractor, '_MAX_ZIP_TOTAL_UNCOMPRESSED_SIZE_BYTES', 5000)
    monkeypatch.setattr(extractor, '_MAX_ZIP_COMPRESSION_RATIO', 1)

    report = extract_import_draft(
        archive_filename='records.zip',
        archive_content=_zip_bytes(
            {
                'valid/one.txt': b'ok',
                'valid/compressed.txt': b'0' * 1000,
            },
            compression=ZIP_DEFLATED,
        ),
    )

    assert report['files_total'] == 1
    assert any('suspiciously compressed file' in warning for warning in report['warnings'])

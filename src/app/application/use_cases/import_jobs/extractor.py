"""Best-effort extraction of useful metadata from arbitrary ZIP archives."""

from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile

try:
    import pydicom
except ImportError:  # pragma: no cover - dependency is expected in runtime.
    pydicom = None  # type: ignore[assignment]

_DATE_PATTERNS = (
    re.compile(r'(?P<year>20\d{2}|19\d{2})[-_. ]?(?P<month>0[1-9]|1[0-2])[-_. ]?(?P<day>0[1-9]|[12]\d|3[01])'),
    re.compile(r'(?P<day>0[1-9]|[12]\d|3[01])[-_. ](?P<month>0[1-9]|1[0-2])[-_. ](?P<year>20\d{2}|19\d{2})'),
)
_CYRILLIC_FIO_RE = re.compile(r'\b[А-ЯЁ][а-яё]+(?:[\s_.-]+[А-ЯЁ][а-яё]+){1,3}\b')
_LATIN_FIO_RE = re.compile(r'\b[A-Z][a-z]+(?:[\s_.-]+[A-Z][a-z]+){1,3}\b')
_TRASH_FILENAMES = {'', '.ds_store', 'thumbs.db', 'desktop.ini'}
_TRASH_PARTS = {'__macosx', '.trash'}
_DICOM_TAGS = (
    'PatientName',
    'PatientBirthDate',
    'StudyDate',
    'SeriesDate',
    'ContentDate',
    'Modality',
    'StudyDescription',
    'SeriesDescription',
    'InstitutionName',
    'StudyInstanceUID',
    'SeriesInstanceUID',
)


@dataclass(slots=True)
class _FileDraft:
    path: str
    filename: str
    size_bytes: int
    mime_type: str
    is_dicom: bool
    patient_fio: str | None
    patient_birth_date: date | None
    event_date: date | None
    record_type: str
    title: str
    group_key: str
    dicom_metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class _PatientDraft:
    candidate_id: str
    fio: str | None
    date_of_birth: date | None
    sources: set[str] = field(default_factory=set)
    files: list[_FileDraft] = field(default_factory=list)


def extract_import_draft(*, archive_filename: str, archive_content: bytes) -> dict[str, object]:
    """Extract patient and record candidates from an arbitrary ZIP archive.

    Args:
        archive_filename: Original uploaded archive filename.
        archive_content: ZIP bytes.

    Returns:
        JSON-serializable draft report for user review.

    """
    warnings: list[str] = []
    archive_fio = _find_fio(archive_filename)
    archive_dates = _find_dates(archive_filename)
    patients: dict[str, _PatientDraft] = {}
    files: list[_FileDraft] = []

    with ZipFile(BytesIO(archive_content)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            path = _safe_zip_path(info.filename)
            if path is None:
                warnings.append(f'Skipped unsafe or system file: {info.filename}')
                continue
            if info.file_size <= 0:
                warnings.append(f'Skipped empty file: {path}')
                continue

            content = archive.read(info)
            dicom_metadata = _read_dicom_metadata(content, path)
            name_context = f'{archive_filename} {path}'
            patient_fio = _dicom_patient_name(dicom_metadata) or _find_fio(path) or archive_fio
            patient_birth_date = _parse_dicom_date(dicom_metadata.get('PatientBirthDate')) or _birth_date_from_dates(
                _find_dates(path),
                archive_dates,
            )
            event_date = _first_date(
                _parse_dicom_date(dicom_metadata.get('StudyDate')),
                _parse_dicom_date(dicom_metadata.get('SeriesDate')),
                _parse_dicom_date(dicom_metadata.get('ContentDate')),
                *_find_dates(path),
            )
            record_type = _guess_record_type(name_context, dicom_metadata)
            group_key = _group_key(path=path, event_date=event_date, record_type=record_type, metadata=dicom_metadata)
            draft = _FileDraft(
                path=path,
                filename=PurePosixPath(path).name,
                size_bytes=info.file_size,
                mime_type=_mime_type(path, bool(dicom_metadata)),
                is_dicom=bool(dicom_metadata),
                patient_fio=patient_fio,
                patient_birth_date=patient_birth_date,
                event_date=event_date,
                record_type=record_type,
                title=_guess_title(path, dicom_metadata),
                group_key=group_key,
                dicom_metadata=dicom_metadata,
            )
            files.append(draft)
            patient_key = _patient_key(patient_fio, patient_birth_date)
            if patient_key not in patients:
                patients[patient_key] = _PatientDraft(
                    candidate_id=f'patient-{len(patients) + 1}',
                    fio=patient_fio,
                    date_of_birth=patient_birth_date,
                )
            patients[patient_key].files.append(draft)
            patients[patient_key].sources.add(path)

    if not patients:
        unknown = _PatientDraft(candidate_id='patient-1', fio=None, date_of_birth=None)
        patients[_patient_key(None, None)] = unknown

    patient_reports = [_patient_to_report(patient) for patient in patients.values()]
    return {
        'message': 'Archive parsed and waiting for user review',
        'source_archive': archive_filename,
        'patients': patient_reports,
        'files_total': len(files),
        'warnings': warnings,
    }


def _patient_to_report(patient: _PatientDraft) -> dict[str, object]:
    groups: dict[str, list[_FileDraft]] = {}
    for file in patient.files:
        groups.setdefault(file.group_key, []).append(file)

    record_groups = []
    for index, group_files in enumerate(groups.values(), start=1):
        representative = group_files[0]
        record_groups.append(
            {
                'group_id': f'{patient.candidate_id}-record-{index}',
                'record_type': representative.record_type,
                'event_date': representative.event_date.isoformat() if representative.event_date else None,
                'title': representative.title,
                'payload_json': {
                    'import_source': 'archive',
                    'dicom_metadata': [item.dicom_metadata for item in group_files if item.dicom_metadata],
                },
                'files': [
                    {
                        'path': item.path,
                        'filename': item.filename,
                        'mime_type': item.mime_type,
                        'size_bytes': item.size_bytes,
                        'is_dicom': item.is_dicom,
                    }
                    for item in group_files
                ],
            },
        )

    return {
        'candidate_id': patient.candidate_id,
        'fio': patient.fio,
        'date_of_birth': patient.date_of_birth.isoformat() if patient.date_of_birth else None,
        'sources': sorted(patient.sources),
        'existing_matches': [],
        'record_groups': record_groups,
    }


def _safe_zip_path(raw_path: str) -> str | None:
    normalized = raw_path.replace('\\', '/').strip('/')
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in {'..', '.'} for part in path.parts):
        return None
    if any(part.casefold() in _TRASH_PARTS for part in path.parts):
        return None
    if path.name.casefold() in _TRASH_FILENAMES:
        return None
    if path.name.startswith('._'):
        return None
    return path.as_posix()


def _read_dicom_metadata(content: bytes, path: str) -> dict[str, object]:
    if pydicom is None:
        return {}
    if not path.lower().endswith(('.dcm', '.dicom', '.ima')) and content[128:132] != b'DICM':
        return {}
    try:
        dataset = pydicom.dcmread(BytesIO(content), stop_before_pixels=True, force=True, specific_tags=_DICOM_TAGS)
    except Exception:
        return {}
    metadata: dict[str, object] = {}
    for tag in _DICOM_TAGS:
        value = getattr(dataset, tag, None)
        if value not in (None, ''):
            metadata[tag] = str(value)
    return metadata


def _find_fio(value: str) -> str | None:
    normalized = _normalize_text(value)
    for pattern in (_CYRILLIC_FIO_RE, _LATIN_FIO_RE):
        match = pattern.search(normalized)
        if match:
            return ' '.join(match.group(0).replace('_', ' ').replace('.', ' ').replace('-', ' ').split())
    return None


def _find_dates(value: str) -> list[date]:
    dates: list[date] = []
    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(value):
            try:
                dates.append(
                    date(
                        int(match.group('year')),
                        int(match.group('month')),
                        int(match.group('day')),
                    ),
                )
            except ValueError:
                continue
    return dates


def _parse_dicom_date(value: object) -> date | None:
    if value is None:
        return None
    raw = str(value)
    if not re.fullmatch(r'\d{8}', raw):
        return None
    try:
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    except ValueError:
        return None


def _dicom_patient_name(metadata: dict[str, object]) -> str | None:
    value = metadata.get('PatientName')
    if value is None:
        return None
    name = str(value).replace('^', ' ')
    return ' '.join(name.split()) or None


def _birth_date_from_dates(path_dates: list[date], archive_dates: list[date]) -> date | None:
    candidates = path_dates or archive_dates
    for candidate in candidates:
        if candidate.year <= date.today().year - 1:
            return candidate
    return None


def _first_date(*values: date | None) -> date | None:
    return next((value for value in values if value is not None), None)


def _guess_record_type(context: str, metadata: dict[str, object]) -> str:
    if metadata:
        return 'exam_result'
    text = context.casefold()
    if any(word in text for word in ('lab', 'анализ', 'лаборат', 'blood', 'биохим')):
        return 'lab_result'
    if any(word in text for word in ('consult', 'консульта', 'прием', 'приём', 'осмотр')):
        return 'consultation_result'
    if any(word in text for word in ('mri', 'мрт', 'ct', 'кт', 'dicom', 'рентген', 'узи', 'study')):
        return 'exam_result'
    return 'other'


def _group_key(
    *,
    path: str,
    event_date: date | None,
    record_type: str,
    metadata: dict[str, object],
) -> str:
    study_uid = metadata.get('StudyInstanceUID')
    if study_uid:
        return f'dicom:{study_uid}'
    if metadata:
        return f'dicom:{event_date}:{metadata.get("Modality", "")}'
    parent = PurePosixPath(path).parent.as_posix()
    return f'file:{parent}:{event_date}:{record_type}'


def _guess_title(path: str, metadata: dict[str, object]) -> str:
    for key in ('StudyDescription', 'SeriesDescription'):
        value = metadata.get(key)
        if value:
            return str(value)[:255]
    name = PurePosixPath(path).parent.name or PurePosixPath(path).stem
    return _normalize_text(name)[:255] or 'Импортированная запись'


def _mime_type(path: str, is_dicom: bool) -> str:
    if is_dicom:
        return 'application/dicom'
    return mimetypes.guess_type(path)[0] or 'application/octet-stream'


def _patient_key(fio: str | None, date_of_birth: date | None) -> str:
    if not fio:
        return 'unknown'
    return f'{fio.casefold()}|{date_of_birth.isoformat() if date_of_birth else ""}'


def _normalize_text(value: str) -> str:
    value = value.replace('\\', '/').replace('/', ' ')
    return re.sub(r'[_\-./()]+', ' ', value)

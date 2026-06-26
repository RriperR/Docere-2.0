"""Best-effort extraction of useful metadata from arbitrary ZIP archives."""

from __future__ import annotations

import mimetypes
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, LargeZipFile, ZipFile

from app.domain.entities.medical_record import MedicalRecordType

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
_MAX_ZIP_FILES = 1000
_MAX_ZIP_FILE_SIZE_BYTES = 100 * 1024 * 1024
_MAX_ZIP_TOTAL_UNCOMPRESSED_SIZE_BYTES = 500 * 1024 * 1024
_MAX_ZIP_COMPRESSION_RATIO = 100
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
_EXPLICIT_BIRTH_DATE_RE = re.compile(
    r'(?:'
    r'date[_\s.-]*of[_\s.-]*birth|birth[_\s.-]*date|birth|dob|'
    r'дата[\s_.-]*рождения|др|д[.\s]*р[.]?|рожд(?:ение|ения)?'
    r')'
    r'[\s_:=-]*'
    r'(?P<date>'
    r'(?:20\d{2}|19\d{2})[-_. ]?(?:0[1-9]|1[0-2])[-_. ]?(?:0[1-9]|[12]\d|3[01])|'
    r'(?:0[1-9]|[12]\d|3[01])[-_. ](?:0[1-9]|1[0-2])[-_. ](?:20\d{2}|19\d{2})'
    r')',
    re.IGNORECASE,
)


class ArchiveExtractionError(ValueError):
    """Archive cannot be parsed as a valid import ZIP."""


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
    event_date_candidates: list[date]
    record_type: MedicalRecordType
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

    Raises:
        ArchiveExtractionError: If archive bytes cannot be read as a valid ZIP.

    """
    warnings: list[str] = []
    archive_fio = _find_fio(archive_filename)
    archive_birth_dates = _find_explicit_birth_dates(archive_filename)
    patients: dict[str, _PatientDraft] = {}
    files: list[_FileDraft] = []
    processed_files = 0
    total_uncompressed_size = 0

    try:
        archive = ZipFile(BytesIO(archive_content))
    except (BadZipFile, LargeZipFile) as error:
        raise ArchiveExtractionError('Archive is not a valid ZIP file') from error

    with archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            path = _safe_zip_path(info.filename)
            if path is None:
                warnings.append(f'Skipped unsafe or system file: {info.filename}')
                continue
            if processed_files >= _MAX_ZIP_FILES:
                warnings.append(f'Skipped file over ZIP file count limit: {path}')
                continue
            if info.file_size <= 0:
                warnings.append(f'Skipped empty file: {path}')
                continue
            if info.file_size > _MAX_ZIP_FILE_SIZE_BYTES:
                warnings.append(f'Skipped file over size limit: {path}')
                continue
            if total_uncompressed_size + info.file_size > _MAX_ZIP_TOTAL_UNCOMPRESSED_SIZE_BYTES:
                warnings.append(f'Skipped file over ZIP total uncompressed size limit: {path}')
                continue
            if _compression_ratio(info.compress_size, info.file_size) > _MAX_ZIP_COMPRESSION_RATIO:
                warnings.append(f'Skipped suspiciously compressed file: {path}')
                continue

            try:
                content = archive.read(info)
            except (BadZipFile, LargeZipFile) as error:
                raise ArchiveExtractionError('Archive contains unreadable ZIP entries') from error
            processed_files += 1
            total_uncompressed_size += info.file_size
            dicom_metadata = _read_dicom_metadata(content, path)
            name_context = f'{archive_filename} {path}'
            patient_fio = _dicom_patient_name(dicom_metadata) or _find_fio(path) or archive_fio
            birth_date_candidates = _unique_dates(
                [
                    *_find_explicit_birth_dates(path),
                    *archive_birth_dates,
                ],
            )
            patient_birth_date = _parse_dicom_date(dicom_metadata.get('PatientBirthDate')) or _single_date_or_none(
                candidates=birth_date_candidates,
                warning_context=f'birth date for {path}',
                warnings=warnings,
            )
            path_dates = [item for item in _find_dates(path) if item not in birth_date_candidates]
            event_date_candidates = _unique_dates([*_dicom_event_dates(dicom_metadata), *path_dates])
            event_date = _single_date_or_none(
                candidates=event_date_candidates,
                warning_context=f'event date for {path}',
                warnings=warnings,
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
                event_date_candidates=event_date_candidates,
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
                'record_type': representative.record_type.value,
                'event_date': representative.event_date.isoformat() if representative.event_date else None,
                'event_date_candidates': [
                    candidate.isoformat()
                    for candidate in _unique_dates(
                        candidate for item in group_files for candidate in item.event_date_candidates
                    )
                ],
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
    raw_path = raw_path.replace('\\', '/')
    if raw_path.startswith('/'):
        return None
    if re.match(r'^[A-Za-z]:[/\\]', raw_path):
        return None

    raw_parts = raw_path.split('/')
    if any(part in {'..', '.'} for part in raw_parts):
        return None
    if any(part.casefold() in _TRASH_PARTS for part in raw_parts):
        return None
    raw_name = raw_parts[-1].casefold() if raw_parts else ''
    if raw_name in _TRASH_FILENAMES:
        return None
    if raw_parts and raw_parts[-1].startswith('._'):
        return None

    normalized = '/'.join(part for part in raw_parts if part)
    if not normalized:
        return None
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in {'..', '.'} for part in path.parts):
        return None
    return path.as_posix()


def _compression_ratio(compressed_size: int, uncompressed_size: int) -> float:
    if compressed_size <= 0:
        return float('inf')
    return uncompressed_size / compressed_size


def _read_dicom_metadata(content: bytes, path: str) -> dict[str, object]:
    if pydicom is None:
        return {}
    if not path.lower().endswith(('.dcm', '.dicom', '.ima')) and content[128:132] != b'DICM':
        return {}
    try:
        dataset = pydicom.dcmread(
            BytesIO(content),
            stop_before_pixels=True,
            force=True,
            specific_tags=list(_DICOM_TAGS),
        )
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


def _find_explicit_birth_dates(value: str) -> list[date]:
    dates: list[date] = []
    for match in _EXPLICIT_BIRTH_DATE_RE.finditer(value):
        dates.extend(_find_dates(match.group('date')))
    return _unique_dates(dates)


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


def _dicom_event_dates(metadata: dict[str, object]) -> list[date]:
    return [
        item
        for item in (
            _parse_dicom_date(metadata.get('StudyDate')),
            _parse_dicom_date(metadata.get('SeriesDate')),
            _parse_dicom_date(metadata.get('ContentDate')),
        )
        if item is not None
    ]


def _dicom_patient_name(metadata: dict[str, object]) -> str | None:
    value = metadata.get('PatientName')
    if value is None:
        return None
    name = str(value).replace('^', ' ')
    return ' '.join(name.split()) or None


def _unique_dates(values: Iterable[date]) -> list[date]:
    return sorted(set(values))


def _single_date_or_none(*, candidates: list[date], warning_context: str, warnings: list[str]) -> date | None:
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        warnings.append(
            f'Multiple date candidates found for {warning_context}: '
            f'{", ".join(candidate.isoformat() for candidate in candidates)}',
        )
    return None


def _guess_record_type(context: str, metadata: dict[str, object]) -> MedicalRecordType:
    if metadata:
        return MedicalRecordType.EXAM_RESULT
    text = context.casefold()
    if any(word in text for word in ('lab', 'анализ', 'лаборат', 'blood', 'биохим')):
        return MedicalRecordType.LAB_RESULT
    if any(word in text for word in ('consult', 'консульта', 'прием', 'приём', 'осмотр')):
        return MedicalRecordType.CONSULTATION_RESULT
    if any(word in text for word in ('mri', 'мрт', 'ct', 'кт', 'dicom', 'рентген', 'узи', 'study')):
        return MedicalRecordType.EXAM_RESULT
    return MedicalRecordType.OTHER


def _group_key(
    *,
    path: str,
    event_date: date | None,
    record_type: MedicalRecordType,
    metadata: dict[str, object],
) -> str:
    study_uid = metadata.get('StudyInstanceUID')
    if study_uid:
        return f'dicom:{study_uid}'
    series_uid = metadata.get('SeriesInstanceUID')
    if series_uid:
        return f'dicom-series:{series_uid}'
    if metadata:
        return f'dicom:{event_date}:{metadata.get("Modality", "")}'
    parent = PurePosixPath(path).parent.as_posix()
    return f'file:{parent}:{event_date}:{record_type.value}'


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

"""Use case извлечения черновика импорта из архива."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from pathlib import PurePosixPath
from uuid import UUID

from app.application.ports.import_jobs.archive_reader import ArchiveReaderPort
from app.application.ports.import_jobs.dicom_metadata_reader import DicomMetadataReaderPort
from app.application.ports.import_jobs.patient_matcher import PatientMatcherPort
from app.application.use_cases.import_jobs.dtos import (
    DicomMetadata,
    ExtractImportDraftCommand,
    ImportDraftResult,
    ImportedFileCandidate,
    PatientCandidate,
    PatientMatchCandidate,
    RecordGroupCandidate,
    RecordType,
)
from app.application.use_cases.import_jobs.errors import ArchiveExtractionError

_DATE_PATTERNS = (
    re.compile(r'(?P<year>20\d{2}|19\d{2})[-_. ]?(?P<month>0[1-9]|1[0-2])[-_. ]?(?P<day>0[1-9]|[12]\d|3[01])'),
    re.compile(r'(?P<day>0[1-9]|[12]\d|3[01])[-_. ](?P<month>0[1-9]|1[0-2])[-_. ](?P<year>20\d{2}|19\d{2})'),
)
_CYRILLIC_FIO_RE = re.compile(r'\b[А-ЯЁ][а-яё]+(?:[\s_.-]+[А-ЯЁ][а-яё]+){1,3}\b')
_LATIN_FIO_RE = re.compile(r'\b[A-Z][a-z]+(?:[\s_.-]+[A-Z][a-z]+){1,3}\b')
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


@dataclass(slots=True)
class _PatientDraft:
    candidate_id: str
    fio: str | None
    date_of_birth: date | None
    sources: set[str] = field(default_factory=set)
    files: list[ImportedFileCandidate] = field(default_factory=list)


class ExtractImportDraftUseCase:
    """Оркестрировать извлечение черновика импорта."""

    def __init__(
        self,
        *,
        archive_reader: ArchiveReaderPort,
        dicom_metadata_reader: DicomMetadataReaderPort,
        patient_matcher: PatientMatcherPort,
    ) -> None:
        """Инициализировать use case зависимостями через порты."""
        self._archive_reader = archive_reader
        self._dicom_metadata_reader = dicom_metadata_reader
        self._patient_matcher = patient_matcher

    def execute(self, command: ExtractImportDraftCommand) -> ImportDraftResult:
        """Извлечь пациентов, группы записей и файлы из архива.

        Returns:
            Типизированный черновик импорта.
        """
        warnings: list[str] = []
        archive_fio = _find_fio(command.archive_filename)
        archive_birth_dates = _find_explicit_birth_dates(command.archive_filename)
        patients: dict[str, _PatientDraft] = {}
        files: list[ImportedFileCandidate] = []

        archive_result = self._archive_reader.read_files(archive_content=command.archive_content)
        warnings.extend(archive_result.warnings)

        for archive_file in archive_result.files:
            dicom_metadata = self._dicom_metadata_reader.read_metadata(
                content=archive_file.content,
                path=archive_file.path,
            )
            name_context = f'{command.archive_filename} {archive_file.path}'
            patient_fio = _dicom_patient_name(dicom_metadata) or _find_fio(archive_file.path) or archive_fio
            birth_date_candidates = _unique_dates(
                [
                    *_find_explicit_birth_dates(archive_file.path),
                    *archive_birth_dates,
                ],
            )
            patient_birth_date = _dicom_patient_birth_date(dicom_metadata) or _single_date_or_none(
                candidates=birth_date_candidates,
                warning_context=f'birth date for {archive_file.path}',
                warnings=warnings,
            )
            path_dates = [item for item in _find_dates(archive_file.path) if item not in birth_date_candidates]
            event_date_candidates = _unique_dates([*_dicom_event_dates(dicom_metadata), *path_dates])
            event_date = _single_date_or_none(
                candidates=event_date_candidates,
                warning_context=f'event date for {archive_file.path}',
                warnings=warnings,
            )
            record_type = _guess_record_type(name_context, dicom_metadata)
            candidate = ImportedFileCandidate(
                path=archive_file.path,
                filename=archive_file.filename,
                size_bytes=archive_file.size_bytes,
                mime_type='application/dicom' if dicom_metadata else archive_file.mime_type,
                is_dicom=dicom_metadata is not None,
                patient_fio=patient_fio,
                patient_birth_date=patient_birth_date,
                event_date=event_date,
                event_date_candidates=tuple(event_date_candidates),
                record_type=record_type,
                title=_guess_title(archive_file.path, dicom_metadata),
                group_key=_group_key(
                    path=archive_file.path,
                    event_date=event_date,
                    record_type=record_type,
                    metadata=dicom_metadata,
                ),
                dicom_metadata=dicom_metadata,
            )
            files.append(candidate)
            patient_key = _patient_key(patient_fio, patient_birth_date)
            if patient_key not in patients:
                patients[patient_key] = _PatientDraft(
                    candidate_id=f'patient-{len(patients) + 1}',
                    fio=patient_fio,
                    date_of_birth=patient_birth_date,
                )
            patients[patient_key].files.append(candidate)
            patients[patient_key].sources.add(archive_file.path)

        if not patients:
            patients[_patient_key(None, None)] = _PatientDraft(
                candidate_id='patient-1',
                fio=None,
                date_of_birth=None,
            )

        return ImportDraftResult(
            message='Archive parsed and waiting for user review',
            source_archive=command.archive_filename,
            patients=tuple(
                self._patient_to_candidate(
                    patient=patient,
                    requested_by_user_id=command.requested_by_user_id,
                    requested_by_role=command.requested_by_role,
                )
                for patient in patients.values()
            ),
            files_total=len(files),
            warnings=tuple(warnings),
        )

    def _patient_to_candidate(
        self,
        *,
        patient: _PatientDraft,
        requested_by_user_id: UUID | None,
        requested_by_role: str | None,
    ) -> PatientCandidate:
        groups: dict[str, list[ImportedFileCandidate]] = {}
        for file in patient.files:
            groups.setdefault(file.group_key, []).append(file)

        record_groups: list[RecordGroupCandidate] = []
        for index, group_files in enumerate(groups.values(), start=1):
            representative = group_files[0]
            record_groups.append(
                RecordGroupCandidate(
                    group_id=f'{patient.candidate_id}-record-{index}',
                    record_type=representative.record_type,
                    event_date=representative.event_date,
                    event_date_candidates=tuple(
                        _unique_dates(candidate for item in group_files for candidate in item.event_date_candidates),
                    ),
                    title=representative.title,
                    payload_json={
                        'import_source': 'archive',
                        'dicom_metadata': [
                            _dicom_metadata_to_payload(item.dicom_metadata)
                            for item in group_files
                            if item.dicom_metadata is not None
                        ],
                    },
                    files=tuple(group_files),
                ),
            )

        existing_matches: tuple[PatientMatchCandidate, ...] = ()
        if patient.fio:
            existing_matches = self._patient_matcher.find_matches(
                fio=patient.fio,
                date_of_birth=patient.date_of_birth,
                requested_by_user_id=requested_by_user_id,
                requested_by_role=requested_by_role,
                limit=5,
            )

        return PatientCandidate(
            candidate_id=patient.candidate_id,
            fio=patient.fio,
            date_of_birth=patient.date_of_birth,
            sources=tuple(sorted(patient.sources)),
            existing_matches=existing_matches,
            record_groups=tuple(record_groups),
        )


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


def _dicom_event_dates(metadata: DicomMetadata | None) -> list[date]:
    if metadata is None:
        return []
    return [
        item
        for item in (
            metadata.study_date,
            metadata.series_date,
            metadata.content_date,
        )
        if item is not None
    ]


def _dicom_patient_name(metadata: DicomMetadata | None) -> str | None:
    if metadata is None or metadata.patient_name is None:
        return None
    name = metadata.patient_name.replace('^', ' ')
    return ' '.join(name.split()) or None


def _dicom_patient_birth_date(metadata: DicomMetadata | None) -> date | None:
    if metadata is None:
        return None
    return metadata.patient_birth_date


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


def _guess_record_type(context: str, metadata: DicomMetadata | None) -> RecordType:
    if metadata is not None:
        return RecordType.EXAM_RESULT
    text = context.casefold()
    if any(word in text for word in ('lab', 'анализ', 'лаборат', 'blood', 'биохим')):
        return RecordType.LAB_RESULT
    if any(word in text for word in ('consult', 'консульта', 'прием', 'приём', 'осмотр')):
        return RecordType.CONSULTATION_RESULT
    if any(word in text for word in ('mri', 'мрт', 'ct', 'кт', 'dicom', 'рентген', 'узи', 'study')):
        return RecordType.EXAM_RESULT
    return RecordType.OTHER


def _group_key(
    *,
    path: str,
    event_date: date | None,
    record_type: RecordType,
    metadata: DicomMetadata | None,
) -> str:
    if metadata is not None:
        if metadata.study_instance_uid:
            return f'dicom:{metadata.study_instance_uid}'
        if metadata.series_instance_uid:
            return f'dicom-series:{metadata.series_instance_uid}'
        return f'dicom:{event_date}:{metadata.modality or ""}'
    parent = PurePosixPath(path).parent.as_posix()
    return f'file:{parent}:{event_date}:{record_type.value}'


def _guess_title(path: str, metadata: DicomMetadata | None) -> str:
    if metadata is not None:
        for value in (metadata.study_description, metadata.series_description):
            if value:
                return value[:255]
    name = PurePosixPath(path).parent.name or PurePosixPath(path).stem
    return _normalize_text(name)[:255] or 'Импортированная запись'


def _patient_key(fio: str | None, date_of_birth: date | None) -> str:
    if not fio:
        return 'unknown'
    return f'{fio.casefold()}|{date_of_birth.isoformat() if date_of_birth else ""}'


def _normalize_text(value: str) -> str:
    value = value.replace('\\', '/').replace('/', ' ')
    return re.sub(r'[_\-./()]+', ' ', value)


def _dicom_metadata_to_payload(metadata: DicomMetadata | None) -> dict[str, object]:
    if metadata is None:
        return {}
    payload: dict[str, object] = {}
    values = {
        'PatientName': metadata.patient_name,
        'PatientBirthDate': metadata.patient_birth_date,
        'StudyDate': metadata.study_date,
        'SeriesDate': metadata.series_date,
        'ContentDate': metadata.content_date,
        'Modality': metadata.modality,
        'StudyDescription': metadata.study_description,
        'SeriesDescription': metadata.series_description,
        'InstitutionName': metadata.institution_name,
        'StudyInstanceUID': metadata.study_instance_uid,
        'SeriesInstanceUID': metadata.series_instance_uid,
    }
    for key, value in values.items():
        if value is None:
            continue
        payload[key] = value.isoformat() if isinstance(value, date) else value
    return payload


__all__ = ('ArchiveExtractionError', 'ExtractImportDraftUseCase')

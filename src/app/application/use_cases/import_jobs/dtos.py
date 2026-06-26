"""DTO use cases ImportJob."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ImportJobDTO:
    """Проекция задания импорта архива."""

    id: UUID
    uploaded_by_user_id: UUID
    status: str
    original_filename: str | None
    archive_storage_key: str | None
    size_bytes: int | None
    report_json: dict[str, object]
    created_at: datetime
    finished_at: datetime | None


class RecordType(StrEnum):
    """Тип медицинской записи в черновике импорта."""

    CONSULTATION_RESULT = 'consultation_result'
    LAB_RESULT = 'lab_result'
    EXAM_RESULT = 'exam_result'
    OTHER = 'other'


@dataclass(frozen=True, slots=True)
class ExtractImportDraftCommand:
    """Команда извлечения черновика импорта из архива."""

    archive_filename: str
    archive_content: bytes
    requested_by_user_id: UUID | None = None
    requested_by_role: str | None = None


@dataclass(frozen=True, slots=True)
class DicomMetadata:
    """Метаданные DICOM, нужные сценарию импорта."""

    patient_name: str | None = None
    patient_birth_date: date | None = None
    study_date: date | None = None
    series_date: date | None = None
    content_date: date | None = None
    modality: str | None = None
    study_description: str | None = None
    series_description: str | None = None
    institution_name: str | None = None
    study_instance_uid: str | None = None
    series_instance_uid: str | None = None


@dataclass(frozen=True, slots=True)
class ImportedFileCandidate:
    """Файл-кандидат, найденный в архиве."""

    path: str
    filename: str
    size_bytes: int
    mime_type: str
    is_dicom: bool
    patient_fio: str | None
    patient_birth_date: date | None
    event_date: date | None
    event_date_candidates: tuple[date, ...]
    record_type: RecordType
    title: str
    group_key: str
    dicom_metadata: DicomMetadata | None = None


@dataclass(frozen=True, slots=True)
class RecordGroupCandidate:
    """Группа файлов, из которой может быть создана медицинская запись."""

    group_id: str
    record_type: RecordType
    event_date: date | None
    event_date_candidates: tuple[date, ...]
    title: str
    payload_json: dict[str, object]
    files: tuple[ImportedFileCandidate, ...]


@dataclass(frozen=True, slots=True)
class PatientMatchCandidate:
    """Существующий пациент, похожий на кандидата из архива."""

    id: str
    fio: str
    date_of_birth: date | None
    status: str
    match_score: float
    match_type: str


@dataclass(frozen=True, slots=True)
class PatientCandidate:
    """Пациент-кандидат, найденный в архиве."""

    candidate_id: str
    fio: str | None
    date_of_birth: date | None
    sources: tuple[str, ...]
    existing_matches: tuple[PatientMatchCandidate, ...]
    record_groups: tuple[RecordGroupCandidate, ...]


@dataclass(frozen=True, slots=True)
class ImportDraftResult:
    """Типизированный результат извлечения черновика импорта."""

    message: str
    source_archive: str
    patients: tuple[PatientCandidate, ...]
    files_total: int
    warnings: tuple[str, ...] = field(default_factory=tuple)

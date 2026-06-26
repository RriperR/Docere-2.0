"""Сериализация черновика импорта для хранения/API."""

from __future__ import annotations

from datetime import date

from app.application.use_cases.import_jobs.dtos import (
    DicomMetadata,
    ImportDraftResult,
    ImportedFileCandidate,
    PatientMatchCandidate,
)


def import_draft_result_to_json(result: ImportDraftResult) -> dict[str, object]:
    """Преобразовать application DTO в JSON-совместимый словарь.

    Returns:
        Словарь для хранения в report_json и отдачи через API-схемы.
    """
    return {
        'message': result.message,
        'source_archive': result.source_archive,
        'patients': [
            {
                'candidate_id': patient.candidate_id,
                'fio': patient.fio,
                'date_of_birth': _date(patient.date_of_birth),
                'sources': list(patient.sources),
                'existing_matches': [_match_to_json(match) for match in patient.existing_matches],
                'record_groups': [
                    {
                        'group_id': group.group_id,
                        'record_type': group.record_type.value,
                        'event_date': _date(group.event_date),
                        'event_date_candidates': [_date(candidate) for candidate in group.event_date_candidates],
                        'title': group.title,
                        'payload_json': group.payload_json,
                        'files': [_file_to_json(file) for file in group.files],
                    }
                    for group in patient.record_groups
                ],
            }
            for patient in result.patients
        ],
        'files_total': result.files_total,
        'warnings': list(result.warnings),
    }


def _file_to_json(file: ImportedFileCandidate) -> dict[str, object]:
    return {
        'path': file.path,
        'filename': file.filename,
        'mime_type': file.mime_type,
        'size_bytes': file.size_bytes,
        'is_dicom': file.is_dicom,
    }


def _match_to_json(match: PatientMatchCandidate) -> dict[str, object]:
    return {
        'id': match.id,
        'fio': match.fio,
        'date_of_birth': _date(match.date_of_birth),
        'status': match.status,
        'match_score': match.match_score,
        'match_type': match.match_type,
    }


def dicom_metadata_to_json(metadata: DicomMetadata) -> dict[str, object]:
    """Преобразовать DICOM DTO в JSON-совместимый словарь.

    Returns:
        JSON-совместимое представление DICOM-метаданных.
    """
    return {
        key: value.isoformat() if isinstance(value, date) else value
        for key, value in {
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
        }.items()
        if value is not None
    }


def _date(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None

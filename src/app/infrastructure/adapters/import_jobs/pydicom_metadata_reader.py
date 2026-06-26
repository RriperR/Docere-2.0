"""pydicom-адаптер чтения DICOM-метаданных."""

from __future__ import annotations

import re
from datetime import date
from io import BytesIO

import pydicom

from app.application.ports.import_jobs.dicom_metadata_reader import DicomMetadataReaderPort
from app.application.use_cases.import_jobs.dtos import DicomMetadata

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


class PydicomMetadataReader(DicomMetadataReaderPort):
    """Извлекает DICOM-метаданные через pydicom."""

    def read_metadata(self, *, content: bytes, path: str) -> DicomMetadata | None:
        """Вернуть метаданные DICOM или None.

        Returns:
            Метаданные DICOM или None, если файл не распознан.
        """
        if not path.lower().endswith(('.dcm', '.dicom', '.ima')) and content[128:132] != b'DICM':
            return None
        try:
            dataset = pydicom.dcmread(
                BytesIO(content),
                stop_before_pixels=True,
                force=True,
                specific_tags=list(_DICOM_TAGS),
            )
        except Exception:
            return None
        return DicomMetadata(
            patient_name=_string_tag(dataset, 'PatientName'),
            patient_birth_date=_dicom_date(_string_tag(dataset, 'PatientBirthDate')),
            study_date=_dicom_date(_string_tag(dataset, 'StudyDate')),
            series_date=_dicom_date(_string_tag(dataset, 'SeriesDate')),
            content_date=_dicom_date(_string_tag(dataset, 'ContentDate')),
            modality=_string_tag(dataset, 'Modality'),
            study_description=_string_tag(dataset, 'StudyDescription'),
            series_description=_string_tag(dataset, 'SeriesDescription'),
            institution_name=_string_tag(dataset, 'InstitutionName'),
            study_instance_uid=_string_tag(dataset, 'StudyInstanceUID'),
            series_instance_uid=_string_tag(dataset, 'SeriesInstanceUID'),
        )


def _string_tag(dataset: object, tag: str) -> str | None:
    value = getattr(dataset, tag, None)
    if value in (None, ''):
        return None
    return str(value)


def _dicom_date(value: str | None) -> date | None:
    if value is None or not re.fullmatch(r'\d{8}', value):
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None

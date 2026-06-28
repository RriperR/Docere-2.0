"""Генерация синтетического архива для демонстрации import review."""

from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, UID

_STUDY_UID = '1.2.826.0.1.3680043.10.543.1'


def build_demo_archive() -> bytes:
    """Сформировать ZIP с безопасными синтетическими медицинскими данными.

    Returns:
        Архив с двумя пациентами, DICOM-группой и review-конфликтами.
    """
    duplicate_date = (date.today() - timedelta(days=10)).isoformat()
    existing_patient = 'Иванов Пётр Васильевич_dob_1990-01-15'
    new_patient = 'Орлова Анна Сергеевна_dob_1988-03-21'
    buffer = BytesIO()
    with ZipFile(buffer, mode='w', compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            f'{existing_patient}/Общий анализ крови/lab_{duplicate_date}.pdf',
            b'%PDF-1.4\nSynthetic Docere demo document\n',
        )
        archive.writestr(
            f'{new_patient}/Консультация/consultation_2026-05-01_2026-05-02.txt',
            'Синтетический документ: требуется выбрать дату события.'.encode(),
        )
        archive.writestr(
            f'{existing_patient}/DICOM/series-a/image-1.dcm',
            _dicom_bytes(series_uid='1.2.826.0.1.3680043.10.543.1.1', instance_number=1),
        )
        archive.writestr(
            f'{existing_patient}/DICOM/series-b/image-2.dcm',
            _dicom_bytes(series_uid='1.2.826.0.1.3680043.10.543.1.2', instance_number=2),
        )
        archive.writestr('../unsafe-demo.txt', b'This entry must be rejected by the archive reader.')
        archive.writestr(f'{new_patient}/empty.txt', b'')
    return buffer.getvalue()


def write_demo_archive(path: Path) -> None:
    """Записать демонстрационный архив по указанному пути.

    Args:
        path: Целевой путь ZIP-файла.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(build_demo_archive())


def _dicom_bytes(*, series_uid: str, instance_number: int) -> bytes:
    buffer = BytesIO()
    instance_uid = f'{series_uid}.{instance_number}'
    file_meta = FileMetaDataset()
    file_meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    file_meta.MediaStorageSOPInstanceUID = UID(instance_uid)
    file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    dataset = FileDataset('demo.dcm', {}, file_meta=file_meta, preamble=b'\0' * 128)
    dataset.SpecificCharacterSet = 'ISO_IR 192'
    dataset.PatientName = 'Иванов^Пётр^Васильевич'
    dataset.PatientBirthDate = '19900115'
    dataset.StudyDate = '20260503'
    dataset.Modality = 'MR'
    dataset.StudyDescription = 'Синтетическое МРТ'
    dataset.SeriesDescription = f'Демо-серия {instance_number}'
    dataset.StudyInstanceUID = _STUDY_UID
    dataset.SeriesInstanceUID = series_uid
    dataset.SOPClassUID = SecondaryCaptureImageStorage
    dataset.SOPInstanceUID = instance_uid
    dataset.save_as(buffer, enforce_file_format=True)
    return buffer.getvalue()

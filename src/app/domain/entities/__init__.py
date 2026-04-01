"""Доменные сущности."""

from app.domain.entities.file_attachment import FileAttachment, FileAttachmentCategory
from app.domain.entities.medical_record import MedicalRecord, MedicalRecordStatus, MedicalRecordType
from app.domain.entities.patient_passport import PatientPassport, PatientPassportStatus
from app.domain.entities.practitioner_passport import PractitionerPassport, PractitionerPassportStatus
from app.domain.entities.record_comment import RecordComment

__all__ = [
    'FileAttachment',
    'FileAttachmentCategory',
    'MedicalRecord',
    'MedicalRecordStatus',
    'MedicalRecordType',
    'PatientPassport',
    'PatientPassportStatus',
    'PractitionerPassport',
    'PractitionerPassportStatus',
    'RecordComment',
]

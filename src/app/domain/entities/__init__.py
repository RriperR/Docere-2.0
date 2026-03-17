"""Доменные сущности."""

from app.domain.entities.medical_record import MedicalRecord, MedicalRecordStatus, MedicalRecordType
from app.domain.entities.patient_passport import PatientPassport, PatientPassportStatus

__all__ = [
    'MedicalRecord',
    'MedicalRecordStatus',
    'MedicalRecordType',
    'PatientPassport',
    'PatientPassportStatus',
]

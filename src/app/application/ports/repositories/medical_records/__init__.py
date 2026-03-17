"""Порт репозитория медицинских записей."""

from app.application.ports.repositories.medical_records.dtos import AccessibleMedicalRecordDTO
from app.application.ports.repositories.medical_records.port import MedicalRecordRepositoryPort

__all__ = ['AccessibleMedicalRecordDTO', 'MedicalRecordRepositoryPort']

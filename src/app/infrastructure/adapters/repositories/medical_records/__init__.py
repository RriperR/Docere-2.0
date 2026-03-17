"""Адаптер репозитория медицинских записей."""

from app.infrastructure.adapters.repositories.medical_records.sqlalchemy_medical_record_repository import (
    SqlAlchemyMedicalRecordRepositoryAdapter,
)

__all__ = ['SqlAlchemyMedicalRecordRepositoryAdapter']

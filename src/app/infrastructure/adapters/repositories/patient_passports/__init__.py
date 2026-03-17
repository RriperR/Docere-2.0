"""Адаптер репозитория паспортов пациентов."""

from app.infrastructure.adapters.repositories.patient_passports.sqlalchemy_patient_passport_repository import (
    SqlAlchemyPatientPassportRepositoryAdapter,
)

__all__ = ['SqlAlchemyPatientPassportRepositoryAdapter']

"""Исключения сценариев работы с медицинскими записями."""


class MedicalRecordError(Exception):
    """Базовая ошибка сценариев работы с медицинскими записями."""


class MedicalRecordNotFoundError(MedicalRecordError):
    """Запись не найдена."""


class MedicalRecordAccessDeniedError(MedicalRecordError):
    """Доступ к записи запрещен."""


class PatientPassportNotFoundError(MedicalRecordError):
    """Паспортная карточка пациента не найдена."""

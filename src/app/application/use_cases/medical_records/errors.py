"""Исключения сценариев работы с медицинскими записями."""


class MedicalRecordError(Exception):
    """Базовая ошибка сценариев медицинских записей."""


class MedicalRecordNotFoundError(MedicalRecordError):
    """Медицинская запись не найдена."""


class MedicalRecordAccessDeniedError(MedicalRecordError):
    """Доступ к медицинской записи запрещен."""


class PatientPassportNotFoundError(MedicalRecordError):
    """Паспорт пациента не найден."""


class PractitionerPassportNotFoundError(MedicalRecordError):
    """Паспорт врача не найден."""


class MedicalRecordValidationError(MedicalRecordError):
    """Бизнес-валидация медицинской записи не пройдена."""

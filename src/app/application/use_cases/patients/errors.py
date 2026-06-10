"""Исключения сценариев работы с карточками пациентов."""


class PatientCardError(Exception):
    """Базовая ошибка сценариев карточек пациентов."""


class PatientCardAccessDeniedError(PatientCardError):
    """Доступ к операции с карточкой пациента запрещен."""


class PatientCardNotFoundError(PatientCardError):
    """Карточка пациента не найдена или недоступна."""

"""Исключения сценариев ImportJob."""


class ImportJobError(Exception):
    """Базовая ошибка ImportJob."""


class ImportJobNotFoundError(ImportJobError):
    """ImportJob не найден или недоступен."""


class ImportJobValidationError(ImportJobError):
    """Архив импорта не прошел валидацию."""


class ArchiveExtractionError(ImportJobError):
    """Архив не может быть прочитан как корректный импортируемый ZIP."""

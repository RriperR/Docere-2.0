"""Исключения сценариев ImportJob."""


class ImportJobError(Exception):
    """Базовая ошибка ImportJob."""


class ImportJobNotFoundError(ImportJobError):
    """ImportJob не найден или недоступен."""


class ImportJobValidationError(ImportJobError):
    """Архив импорта не прошел валидацию."""


class ImportJobDuplicateConfirmationRequiredError(ImportJobValidationError):
    """Для похожей существующей записи требуется явное подтверждение."""

    def __init__(self, *, group_id: str) -> None:
        """Сохранить идентификатор неоднозначной группы.

        Args:
            group_id: Идентификатор группы импортируемой записи.
        """
        self.group_id = group_id
        super().__init__(f'Duplicate confirmation required for group {group_id}')


class ArchiveExtractionError(ImportJobError):
    """Архив не может быть прочитан как корректный импортируемый ZIP."""

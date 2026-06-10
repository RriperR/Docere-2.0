"""Исключения сценариев sharing-запросов."""


class ShareRequestError(Exception):
    """Базовая ошибка сценариев sharing-запросов."""


class ShareRequestAccessDeniedError(ShareRequestError):
    """Операция над sharing-запросом запрещена."""


class ShareRequestNotFoundError(ShareRequestError):
    """Sharing-запрос не найден."""


class ShareTargetNotFoundError(ShareRequestError):
    """Получатель sharing-запроса не найден."""


class SharedRecordNotFoundError(ShareRequestError):
    """Медицинская запись для sharing не найдена."""

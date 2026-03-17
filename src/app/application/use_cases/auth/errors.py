"""Исключения сценариев аутентификации."""


class AuthError(Exception):
    """Базовая ошибка сценариев аутентификации."""


class EmailAlreadyExistsError(AuthError):
    """Пользователь с таким email уже существует."""


class InvalidCredentialsError(AuthError):
    """Переданы некорректные учетные данные."""


class InvalidTokenError(AuthError):
    """Передан некорректный или истекший access-токен."""


class InvalidRefreshTokenError(AuthError):
    """Передан некорректный или истекший refresh-токен."""


class UserNotFoundError(AuthError):
    """Пользователь не найден."""

"""Конфигурация приложения и фабрики настроек."""

from functools import lru_cache

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    """Настройки подключения к базе данных."""

    url: str


class AuthSettings(BaseModel):
    """Настройки аутентификации и JWT."""

    secret_key: SecretStr
    access_token_ttl_minutes: int = 60
    refresh_token_ttl_minutes: int = 10_080
    jwt_algorithm: str = 'HS256'


class StorageSettings(BaseModel):
    """Настройки файлового хранилища."""

    endpoint: str
    bucket: str


class QueueSettings(BaseModel):
    """Настройки очереди фоновых задач."""

    broker_url: str
    result_backend: str | None = None


class AppSettings(BaseSettings):
    """Корневой объект конфигурации приложения."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix='APP_',
        env_nested_delimiter='__',
        extra='ignore',
        case_sensitive=False,
    )

    service_name: str = 'docere-service'
    database: DatabaseSettings
    auth: AuthSettings
    storage: StorageSettings
    queue: QueueSettings


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Получить и закешировать настройки приложения.

    Returns:
        Валидированные настройки приложения.
    """
    return AppSettings()


def clear_settings_cache() -> None:
    """Очистить кеш объекта настроек."""
    get_settings.cache_clear()


def validate_settings() -> AppSettings:
    """Проверить, что настройки приложения валидны.

    Returns:
        Валидированные настройки приложения.
    """
    return get_settings()

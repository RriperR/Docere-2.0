"""Конфигурация приложения и фабрики настроек."""

from functools import cache
from pathlib import Path

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.infrastructure.config.paths import DEFAULT_ENV_FILE


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


@cache
def get_settings(*, env_file: Path | None = DEFAULT_ENV_FILE) -> AppSettings:
    """Получить и закешировать настройки приложения.

    Args:
        env_file: Путь до dotenv-файла. `None` отключает чтение `.env`.

    Returns:
        Валидированные настройки приложения.
    """
    return AppSettings(_env_file=env_file)


def clear_settings_cache() -> None:
    """Очистить кеш объекта настроек."""
    get_settings.cache_clear()

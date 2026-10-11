"""Конфигурация приложения и фабрики настроек."""

from functools import cache
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.import_ai import AiOptions
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
    """Настройки файлового хранилища (S3/MinIO)."""

    endpoint: str
    bucket: str
    access_key: str = 'minioadmin'
    secret_key: SecretStr = SecretStr('minioadmin')
    region: str = 'us-east-1'


class QueueSettings(BaseModel):
    """Настройки очереди фоновых задач."""

    broker_url: str
    result_backend: str | None = None


class ImportArchiveSettings(BaseModel):
    """Настройки обработки импортируемых ZIP-архивов."""

    max_files: int = 1000
    max_file_size_bytes: int = 100 * 1024 * 1024
    max_total_uncompressed_size_bytes: int = 500 * 1024 * 1024
    max_compression_ratio: int = 100


class ImportAiSettings(BaseModel):
    """Настройки внешнего AI; токен не попадает в публичные ответы."""

    enabled: bool = False
    provider: str = 'AI-сервис'
    base_url: str = ''
    model: str = ''
    token: SecretStr = SecretStr('')
    timeout_seconds: float = Field(default=60, gt=0, le=120)
    max_documents: int = Field(default=20, ge=1, le=100)
    max_pages: int = Field(default=100, ge=1, le=1000)
    max_pages_per_document: int = Field(default=30, ge=1, le=100)
    batch_pages: int = Field(default=5, ge=1, le=10)
    concurrency: int = Field(default=2, ge=1, le=10)

    def options(self) -> AiOptions:
        """Вернуть не секретную конфигурацию; неполное подключение недоступно.

        Returns:
            Параметры с безопасным признаком готовности.
        """
        return AiOptions(
            enabled=self.enabled and bool(self.base_url and self.model and self.token.get_secret_value()),
            provider=self.provider,
            model=self.model,
            max_documents=self.max_documents,
            max_pages=self.max_pages,
            max_pages_per_document=self.max_pages_per_document,
            batch_pages=self.batch_pages,
            concurrency=self.concurrency,
        )


class AppSettings(BaseSettings):
    """Корневой объект конфигурации приложения."""

    model_config = SettingsConfigDict(
        env_prefix='APP_',
        env_nested_delimiter='__',
        extra='ignore',
        case_sensitive=False,
    )

    service_name: str = 'docere-service'
    graceful_shutdown_reject_window_seconds: float = 1.0
    database: DatabaseSettings
    auth: AuthSettings
    storage: StorageSettings
    queue: QueueSettings
    import_archive: ImportArchiveSettings = ImportArchiveSettings()
    import_ai: ImportAiSettings = ImportAiSettings()


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

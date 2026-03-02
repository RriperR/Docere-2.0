from functools import lru_cache

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseModel):
    url: str


class AuthSettings(BaseModel):
    secret_key: SecretStr
    access_token_ttl_minutes: int = 60
    jwt_algorithm: str = 'HS256'


class StorageSettings(BaseModel):
    endpoint: str
    bucket: str


class QueueSettings(BaseModel):
    broker_url: str
    result_backend: str | None = None


class AppSettings(BaseSettings):
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


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()


def validate_settings() -> AppSettings:
    return get_settings()

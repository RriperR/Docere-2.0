from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='APP_', extra='ignore')

    service_name: str = 'docere-service'

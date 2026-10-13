"""Настройки сервиса извлечения атрибутов."""

from pydantic_settings import BaseSettings, SettingsConfigDict

from attribute_extractor.constants import API_PREFIX


class Settings(BaseSettings):
    """Настройки, читаемые из переменных окружения с префиксом ``EXTRACTOR_``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EXTRACTOR_",
        extra="ignore",
    )

    app_name: str = "SpecFlow Attribute Extractor"
    api_prefix: str = API_PREFIX


settings = Settings()

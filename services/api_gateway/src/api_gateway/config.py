"""Настройки API Gateway."""

from pydantic_settings import BaseSettings, SettingsConfigDict

from api_gateway.constants import (
    API_PREFIX,
    DEFAULT_CORS_ORIGINS,
    DEFAULT_EXTRACTOR_URL,
    DEFAULT_UPSTREAM_TIMEOUT_SECONDS,
)


class Settings(BaseSettings):
    """Настройки, читаемые из переменных окружения с префиксом ``API_GATEWAY_``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="API_GATEWAY_",
        extra="ignore",
    )

    app_name: str = "SpecFlow API Gateway"
    api_prefix: str = API_PREFIX
    cors_origins: list[str] = DEFAULT_CORS_ORIGINS
    attribute_extractor_url: str = DEFAULT_EXTRACTOR_URL
    upstream_timeout_seconds: float = DEFAULT_UPSTREAM_TIMEOUT_SECONDS


settings = Settings()

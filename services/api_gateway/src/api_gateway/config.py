"""Настройки API Gateway."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from api_gateway.constants import (
    API_PREFIX,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_CORS_ORIGINS,
    DEFAULT_EXTRACTOR_URL,
    DEFAULT_MAX_BATCH_SIZE,
    DEFAULT_PIPELINE_VERSION,
    DEFAULT_UPSTREAM_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_UPSTREAM_TIMEOUT_SECONDS,
    MAX_CONFIDENCE,
    MIN_BATCH_SIZE,
    MIN_CONFIDENCE,
    SERVICE_VERSION,
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

    # Версии сервиса и пайплайна (публикуются в ``/health`` и ``/info``).
    service_version: str = SERVICE_VERSION
    pipeline_version: str = DEFAULT_PIPELINE_VERSION

    # Порог уверенности и лимит батча публичного API.
    default_confidence_threshold: float = Field(
        DEFAULT_CONFIDENCE_THRESHOLD, ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE
    )
    max_batch_size: int = Field(
        DEFAULT_MAX_BATCH_SIZE, ge=MIN_BATCH_SIZE, le=DEFAULT_MAX_BATCH_SIZE
    )

    # Внешние подключения.
    cors_origins: list[str] = DEFAULT_CORS_ORIGINS
    attribute_extractor_url: str = DEFAULT_EXTRACTOR_URL
    upstream_timeout_seconds: float = Field(DEFAULT_UPSTREAM_TIMEOUT_SECONDS, gt=0.0)
    upstream_connect_timeout_seconds: float = Field(
        DEFAULT_UPSTREAM_CONNECT_TIMEOUT_SECONDS, gt=0.0
    )


settings = Settings()

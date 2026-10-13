"""Настройки API Gateway."""

from pydantic_settings import BaseSettings, SettingsConfigDict

from api_gateway.constants import API_PREFIX, DEFAULT_CORS_ORIGINS


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
    attribute_extractor_url: str = "http://attribute_extractor:8001"


settings = Settings()

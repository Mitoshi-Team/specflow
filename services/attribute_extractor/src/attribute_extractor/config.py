"""Настройки сервиса извлечения атрибутов."""

from pydantic_settings import BaseSettings, SettingsConfigDict

from attribute_extractor.constants import (
    API_PREFIX,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_HYBRID_STRATEGY,
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_MAX_BATCH_SIZE,
    DEFAULT_PIPELINE_VERSION,
    REVIEW_CONFIDENCE_THRESHOLD,
)


class Settings(BaseSettings):
    """Настройки, читаемые из переменных окружения с префиксом ``EXTRACTOR_``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EXTRACTOR_",
        extra="ignore",
    )

    app_name: str = "SpecFlow Attribute Extractor"
    api_prefix: str = API_PREFIX
    pipeline_version: str = DEFAULT_PIPELINE_VERSION

    # Пороги уверенности и пакетная обработка.
    default_confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    review_confidence_threshold: float = REVIEW_CONFIDENCE_THRESHOLD
    max_batch_size: int = DEFAULT_MAX_BATCH_SIZE

    # Гибридный пайплайн и обязательные проверки.
    hybrid_strategy: str = DEFAULT_HYBRID_STRATEGY
    grounding_required: bool = True
    normalization_enabled: bool = True
    unit_conversion_enabled: bool = True
    enum_strict: bool = False

    # Внешняя LLM (по умолчанию выключена: базовый режим работает на правилах).
    enable_llm: bool = False
    llm_provider: str = DEFAULT_LLM_PROVIDER
    llm_model: str = ""
    llm_api_key: str = ""
    llm_temperature: float = DEFAULT_LLM_TEMPERATURE
    llm_max_tokens: int = DEFAULT_LLM_MAX_TOKENS


settings = Settings()

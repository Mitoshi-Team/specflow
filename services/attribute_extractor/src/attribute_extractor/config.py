"""Настройки сервиса извлечения атрибутов."""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from attribute_extractor.constants import (
    API_PREFIX,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_ENABLE_NER,
    DEFAULT_ENABLE_RULES,
    DEFAULT_ENABLE_RULES_FALLBACK,
    DEFAULT_ENABLE_VECTOR_MATCH,
    DEFAULT_ENUM_STRICT,
    DEFAULT_GROUNDING_REQUIRED,
    DEFAULT_MATCH_THRESHOLD,
    DEFAULT_MAX_BATCH_SIZE,
    DEFAULT_NER_MODEL_VERSION,
    DEFAULT_NORMALIZATION_ENABLED,
    DEFAULT_PIPELINE_VERSION,
    DEFAULT_RULES_VERSION,
    DEFAULT_UNIT_CONVERSION_ENABLED,
    DEFAULT_VECTOR_BACKEND,
    DEFAULT_VECTOR_K,
    DEFAULT_VOCAB_VERSION,
    MAX_CONFIDENCE,
    MIN_BATCH_SIZE,
    MIN_CONFIDENCE,
    REVIEW_CONFIDENCE_THRESHOLD,
    SERVICE_VERSION,
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

    # Версии сервиса, пайплайна и компонентов (используются в трассировке).
    service_version: str = SERVICE_VERSION
    pipeline_version: str = DEFAULT_PIPELINE_VERSION
    rules_version: str = DEFAULT_RULES_VERSION
    vocab_version: str = DEFAULT_VOCAB_VERSION
    ner_model_version: str = DEFAULT_NER_MODEL_VERSION

    # Пороги уверенности.
    default_confidence_threshold: float = Field(
        DEFAULT_CONFIDENCE_THRESHOLD, ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE
    )
    review_confidence_threshold: float = Field(
        REVIEW_CONFIDENCE_THRESHOLD, ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE
    )

    # Пакетная обработка.
    min_batch_size: int = MIN_BATCH_SIZE
    max_batch_size: int = Field(
        DEFAULT_MAX_BATCH_SIZE, ge=MIN_BATCH_SIZE, le=DEFAULT_MAX_BATCH_SIZE
    )
    # Обязательные проверки и нормализация.
    grounding_required: bool = DEFAULT_GROUNDING_REQUIRED
    normalization_enabled: bool = DEFAULT_NORMALIZATION_ENABLED
    unit_conversion_enabled: bool = DEFAULT_UNIT_CONVERSION_ENABLED
    enum_strict: bool = DEFAULT_ENUM_STRICT

    # Тумблеры этапов пайплайна.
    enable_rules: bool = DEFAULT_ENABLE_RULES
    enable_ner: bool = DEFAULT_ENABLE_NER
    enable_vector_match: bool = DEFAULT_ENABLE_VECTOR_MATCH
    enable_rules_fallback: bool = DEFAULT_ENABLE_RULES_FALLBACK

    # Резолв поля (векторный матч).
    vector_backend: Literal["auto", "embedding", "lexical"] = DEFAULT_VECTOR_BACKEND
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    match_threshold: float = Field(DEFAULT_MATCH_THRESHOLD, ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE)
    vector_k: int = Field(DEFAULT_VECTOR_K, ge=1)

    @model_validator(mode="after")
    def _validate_threshold_order(self) -> "Settings":
        """Порог ручной проверки не может превышать порог автоматизации."""
        if self.review_confidence_threshold > self.default_confidence_threshold:
            raise ValueError(
                "review_confidence_threshold не может превышать default_confidence_threshold"
            )
        return self


settings = Settings()

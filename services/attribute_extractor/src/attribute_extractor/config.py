"""Настройки сервиса извлечения атрибутов."""

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from attribute_extractor.constants import (
    API_PREFIX,
    DEFAULT_CATEGORY_SCHEMAS_PATH,
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
    DEFAULT_NER_MODEL_PATH,
    DEFAULT_NER_MODEL_VERSION,
    DEFAULT_NER_SPAN_MIN_SCORE,
    DEFAULT_NORMALIZATION_ENABLED,
    DEFAULT_PIPELINE_VERSION,
    DEFAULT_RATE_LIMIT_REQUESTS,
    DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
    DEFAULT_RULES_VERSION,
    DEFAULT_UNIT_CONVERSION_ENABLED,
    DEFAULT_VECTOR_BACKEND,
    DEFAULT_VECTOR_K,
    DEFAULT_VOCAB_VERSION,
    DETERMINISTIC_CONFIDENCE,
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

    # Реестр схем категорий: артефакт scripts/build_category_schemas.py,
    # загружается на старте; отсутствие файла — штатный generic-fallback.
    category_schemas_path: str = DEFAULT_CATEGORY_SCHEMAS_PATH

    # Версии сервиса, пайплайна и компонентов (используются в трассировке).
    service_version: str = SERVICE_VERSION
    pipeline_version: str = DEFAULT_PIPELINE_VERSION
    rules_version: str = DEFAULT_RULES_VERSION
    vocab_version: str = DEFAULT_VOCAB_VERSION
    ner_model_version: str = DEFAULT_NER_MODEL_VERSION
    ner_model_path: str = DEFAULT_NER_MODEL_PATH

    # Пороги уверенности.
    default_confidence_threshold: float = Field(
        DEFAULT_CONFIDENCE_THRESHOLD, ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE
    )
    review_confidence_threshold: float = Field(
        REVIEW_CONFIDENCE_THRESHOLD, ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE
    )
    deterministic_confidence: float = Field(
        DETERMINISTIC_CONFIDENCE, ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE
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

    # NER: каталог весов и порог уверенности спанов (precision-first).
    ner_model_path: str = DEFAULT_NER_MODEL_PATH
    ner_span_min_score: float = Field(
        DEFAULT_NER_SPAN_MIN_SCORE, ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE
    )

    # Rate limiting (429); 0 запросов — ограничение выключено.
    rate_limit_requests: int = Field(DEFAULT_RATE_LIMIT_REQUESTS, ge=0)
    rate_limit_window_seconds: float = Field(DEFAULT_RATE_LIMIT_WINDOW_SECONDS, gt=0)

    # Серверная история батчей (PostgreSQL). Пусто — хранилище в памяти процесса
    # (dev без БД; история не переживает перезапуск — см. batch_store.py).
    database_url: str = ""

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    @model_validator(mode="after")
    def _validate_threshold_order(self) -> "Settings":
        """Порог ручной проверки не может превышать порог автоматизации."""
        if self.review_confidence_threshold > self.default_confidence_threshold:
            raise ValueError(
                "review_confidence_threshold не может превышать default_confidence_threshold"
            )
        return self


settings = Settings()

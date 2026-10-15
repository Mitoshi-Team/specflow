"""Настройки сервиса извлечения атрибутов."""

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from attribute_extractor.constants import (
    API_PREFIX,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_ENABLE_LLM,
    DEFAULT_ENUM_STRICT,
    DEFAULT_GROUNDING_REQUIRED,
    DEFAULT_HYBRID_STRATEGY,
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_MODEL,
    DEFAULT_LLM_PROVIDER,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    DEFAULT_MAX_BATCH_SIZE,
    DEFAULT_METHOD_WEIGHTS,
    DEFAULT_NER_MODEL_VERSION,
    DEFAULT_NORMALIZATION_ENABLED,
    DEFAULT_PIPELINE_VERSION,
    DEFAULT_RULES_VERSION,
    DEFAULT_TRANSFORMER_MODEL_VERSION,
    DEFAULT_UNIT_CONVERSION_ENABLED,
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
    transformer_model_version: str = DEFAULT_TRANSFORMER_MODEL_VERSION

    # Пороги уверенности и веса методов агрегации.
    default_confidence_threshold: float = Field(
        DEFAULT_CONFIDENCE_THRESHOLD, ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE
    )
    review_confidence_threshold: float = Field(
        REVIEW_CONFIDENCE_THRESHOLD, ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE
    )
    method_weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_METHOD_WEIGHTS))

    # Пакетная обработка.
    min_batch_size: int = MIN_BATCH_SIZE
    max_batch_size: int = Field(
        DEFAULT_MAX_BATCH_SIZE, ge=MIN_BATCH_SIZE, le=DEFAULT_MAX_BATCH_SIZE
    )

    # Гибридный пайплайн и обязательные проверки.
    hybrid_strategy: str = DEFAULT_HYBRID_STRATEGY
    grounding_required: bool = DEFAULT_GROUNDING_REQUIRED
    normalization_enabled: bool = DEFAULT_NORMALIZATION_ENABLED
    unit_conversion_enabled: bool = DEFAULT_UNIT_CONVERSION_ENABLED
    enum_strict: bool = DEFAULT_ENUM_STRICT

    # Внешняя LLM (по умолчанию выключена: базовый режим работает на правилах).
    enable_llm: bool = DEFAULT_ENABLE_LLM
    llm_provider: str = DEFAULT_LLM_PROVIDER
    llm_model: str = DEFAULT_LLM_MODEL
    llm_api_key: str = ""
    llm_temperature: float = Field(DEFAULT_LLM_TEMPERATURE, ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE)
    llm_max_tokens: int = Field(DEFAULT_LLM_MAX_TOKENS, gt=0)
    llm_timeout_seconds: float = Field(DEFAULT_LLM_TIMEOUT_SECONDS, gt=0.0)

    @field_validator("method_weights")
    @classmethod
    def _validate_method_weights(cls, weights: dict[str, float]) -> dict[str, float]:
        """Веса методов должны лежать в шкале уверенности [0, 1]."""
        for method, weight in weights.items():
            if not MIN_CONFIDENCE <= weight <= MAX_CONFIDENCE:
                raise ValueError(
                    f"Вес метода '{method}' должен быть в диапазоне "
                    f"[{MIN_CONFIDENCE}, {MAX_CONFIDENCE}]"
                )
        return weights

    @model_validator(mode="after")
    def _validate_threshold_order(self) -> "Settings":
        """Порог ручной проверки не может превышать порог автоматизации."""
        if self.review_confidence_threshold > self.default_confidence_threshold:
            raise ValueError(
                "review_confidence_threshold не может превышать default_confidence_threshold"
            )
        return self


settings = Settings()

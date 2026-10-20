"""Pydantic-схемы API-контракта SpecFlow (openspec/specs/api_contract.md).

Схемы описывают тела запросов и ответов публичного REST API. Доменные модели
переиспользуются там, где контракт совпадает с ними (``CategorySchema``,
``ExtractionResult``, ``Span``).
"""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from specflow_contracts.constants import (
    DEFAULT_RETURN_RAW_VALUES,
    DEFAULT_RETURN_SOURCES,
    MAX_BATCH_SIZE,
    MAX_CONFIDENCE,
    MAX_TEXT_LENGTH,
    MIN_BATCH_SIZE,
    MIN_CONFIDENCE,
)
from specflow_contracts.domain import ExtractionResult, ProductCard
from specflow_contracts.enums import HealthStatus


class ProductCardRequest(ProductCard):
    """Запрос на извлечение по одной карточке (``POST /api/v1/extract``)."""

    @model_validator(mode="after")
    def _require_text(self) -> "ProductCardRequest":
        if not self.has_text_content():
            raise ValueError(
                "Хотя бы одно из полей title, description, seller_attributes должно быть непустым"
            )
        return self

    @model_validator(mode="after")
    def _limit_text_size(self) -> "ProductCardRequest":
        """Soft-limit: слишком большое описание отклоняется с понятной 422 (api_contract.md, 5)."""
        text_length = len(self.title or "") + len(self.description or "")
        if text_length > MAX_TEXT_LENGTH:
            raise ValueError(
                f"Суммарная длина title и description не должна превышать {MAX_TEXT_LENGTH} "
                f"символов (получено {text_length})"
            )
        return self


class BatchExtractRequest(BaseModel):
    """Запрос пакетного извлечения (``POST /api/v1/extract/batch``)."""

    items: list[ProductCardRequest] = Field(min_length=MIN_BATCH_SIZE, max_length=MAX_BATCH_SIZE)
    batch_id: str | None = None
    batch_size: int | None = Field(default=None, ge=MIN_BATCH_SIZE, le=MAX_BATCH_SIZE)
    return_sources: bool = DEFAULT_RETURN_SOURCES
    return_raw_values: bool = DEFAULT_RETURN_RAW_VALUES
    threshold_override: float | None = Field(default=None, ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE)


class BatchExtractResponse(BaseModel):
    """Ответ пакетного извлечения с частичным успехом по каждой карточке."""

    total: int
    ok: int
    low_confidence: int
    errors: int
    results: list[ExtractionResult] = Field(default_factory=list)
    batch_id: str | None = None
    processing_time_ms_total: int | None = None
    # Сервер выставляет признак явно: False — запись в историю не удалась
    # (причина в логе сервиса), клиенту показывается предупреждение о риске
    # потери результатов (api_contract.md, 3.5/4.2).
    persisted: bool = True


class BatchSummary(BaseModel):
    """Краткая сводка сохранённого батча (``GET /api/v1/batches``)."""

    batch_id: str
    created_at: datetime
    total: int
    ok: int
    low_confidence: int
    errors: int
    threshold: float | None = None


class BatchListResponse(BaseModel):
    """История батчей, новые первыми (``GET /api/v1/batches``)."""

    items: list[BatchSummary]
    total: int


class StoredBatchResponse(BaseModel):
    """Полностью сохранённый батч (``GET /api/v1/batches/{batch_id}``)."""

    batch_id: str
    created_at: datetime
    threshold: float | None = None
    cards: list[ProductCardRequest] = Field(default_factory=list)
    response: BatchExtractResponse


class HealthResponse(BaseModel):
    """Ответ проверки работоспособности (``GET /api/v1/health``)."""

    status: HealthStatus
    version: str
    pipeline_version: str
    models_loaded: list[str] = Field(default_factory=list)
    uptime_seconds: int | None = None
    cache_enabled: bool = False


class ErrorDetail(BaseModel):
    """Детализация одной ошибки валидации."""

    msg: str
    type: str
    loc: list[str | int] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Унифицированный ответ об ошибке."""

    detail: str
    code: str | None = None
    errors: list[ErrorDetail] | None = None

"""Доменные модели пайплайна извлечения атрибутов.

Модели описывают базовый контракт «вход → выход»: на входе ``ProductCard``,
на выходе ``ExtractionResult`` со списком ``AttributeCandidate``. Модели
используются как общий источник правды для сервисов API Gateway и Attribute
Extractor (см. openspec/specs/domain-model.md).
"""

from typing import Any

from pydantic import BaseModel, Field, computed_field

from specflow_contracts.constants import MAX_CONFIDENCE, MIN_CONFIDENCE
from specflow_contracts.enums import (
    AttributeValueType,
    ExtractionMethod,
    ExtractionStatus,
    SpanField,
)


class Span(BaseModel):
    """Фрагмент исходного текста, подтверждающий извлечённое значение."""

    field: SpanField
    text: str
    start: int | None = None
    end: int | None = None


class ProductCard(BaseModel):
    """Входная карточка товара. Используется только текстовая часть."""

    product_id: str | None = None
    title: str | None = None
    description: str | None = None
    seller_attributes: dict[str, Any] | list[Any] | None = None
    category_id: str | None = None
    category_name: str | None = None
    language: str | None = None

    def has_text_content(self) -> bool:
        """Есть ли в карточке хотя бы одно непустое текстовое поле."""
        if self.title and self.title.strip():
            return True
        if self.description and self.description.strip():
            return True
        return bool(self.seller_attributes)

    @computed_field
    @property
    def raw_text(self) -> str:
        """Конкатенированный текст карточки для анализа."""
        parts = [part for part in (self.title, self.description) if part]
        if self.seller_attributes:
            parts.append(str(self.seller_attributes))
        return " ".join(parts)


class Attribute(BaseModel):
    """Описание атрибута в схеме категории."""

    code: str
    value_type: AttributeValueType
    name_ru: str | None = None
    category_scope: list[str] | None = None
    is_required: bool = False
    unit: str | None = None
    allow_multiple: bool = False
    synonyms: list[str] | None = None
    vocab: list[str] | None = None
    normalization_rules: dict[str, Any] | None = None


class CategorySchema(BaseModel):
    """Схема обязательных и ключевых атрибутов категории."""

    category: str
    schema_version: str
    category_id: str | None = None
    required_attributes: list[Attribute] = Field(default_factory=list)
    optional_attributes: list[Attribute] = Field(default_factory=list)


class AttributeCandidate(BaseModel):
    """Кандидат значения атрибута, извлечённый из текста карточки."""

    attribute_code: str
    raw_value: str
    normalized_value: str
    confidence: float = Field(ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE)
    extraction_method: ExtractionMethod
    is_confirmed_in_text: bool
    source_spans: list[Span] = Field(default_factory=list)
    evidence_text: str | None = None
    features: dict[str, Any] | None = None


class ExtractionResult(BaseModel):
    """Структурированный результат извлечения по одной карточке."""

    attributes: list[AttributeCandidate] = Field(default_factory=list)
    status: ExtractionStatus
    needs_review: bool
    pipeline_version: str
    product_id: str | None = None
    category_id: str | None = None
    category_name: str | None = None
    low_confidence_count: int | None = None
    processing_time_ms: int | None = None

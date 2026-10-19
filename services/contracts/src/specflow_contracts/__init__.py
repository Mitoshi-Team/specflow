"""Общие доменные модели и Pydantic-схемы сервисов SpecFlow."""

from specflow_contracts.api import (
    BatchExtractRequest,
    BatchExtractResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    ProductCardRequest,
)
from specflow_contracts.domain import (
    Attribute,
    AttributeCandidate,
    CategorySchema,
    ExtractionResult,
    ProductCard,
    Span,
)
from specflow_contracts.enums import (
    AttributeValueType,
    ErrorCode,
    ExtractionMethod,
    ExtractionStatus,
    HealthStatus,
    SpanField,
)

__all__ = [
    "Attribute",
    "AttributeCandidate",
    "AttributeValueType",
    "BatchExtractRequest",
    "BatchExtractResponse",
    "CategorySchema",
    "ErrorDetail",
    "ErrorCode",
    "ErrorResponse",
    "ExtractionMethod",
    "ExtractionResult",
    "ExtractionStatus",
    "HealthResponse",
    "HealthStatus",
    "ProductCard",
    "ProductCardRequest",
    "Span",
    "SpanField",
]

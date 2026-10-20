"""Общие доменные модели и Pydantic-схемы сервисов SpecFlow."""

from specflow_contracts.api import (
    BatchExtractRequest,
    BatchExtractResponse,
    BatchListResponse,
    BatchSummary,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    ProductCardRequest,
    StoredBatchResponse,
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
    "BatchListResponse",
    "BatchSummary",
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
    "StoredBatchResponse",
]

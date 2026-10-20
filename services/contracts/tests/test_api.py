from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

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
from specflow_contracts.constants import MAX_BATCH_SIZE, MAX_TEXT_LENGTH
from specflow_contracts.domain import AttributeCandidate, ExtractionResult
from specflow_contracts.enums import (
    ErrorCode,
    ExtractionMethod,
    ExtractionStatus,
    HealthStatus,
)


def test_product_card_request_accepts_title_only() -> None:
    request = ProductCardRequest(title="Смартфон Samsung")

    assert request.title == "Смартфон Samsung"


def test_product_card_request_accepts_seller_attributes_only() -> None:
    request = ProductCardRequest(seller_attributes={"brand": "Samsung"})

    assert request.seller_attributes == {"brand": "Samsung"}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": "   "},
        {"description": ""},
        {"seller_attributes": {}},
        {"seller_attributes": []},
    ],
)
def test_product_card_request_rejects_empty_payload(payload: dict) -> None:
    with pytest.raises(ValidationError):
        ProductCardRequest(**payload)


def test_product_card_request_accepts_text_at_soft_limit() -> None:
    """Граница soft-limit: ровно MAX_TEXT_LENGTH символов допускается."""
    request = ProductCardRequest(description="а" * MAX_TEXT_LENGTH)

    assert request.description == "а" * MAX_TEXT_LENGTH


def test_product_card_request_rejects_oversized_text() -> None:
    """Soft-limit (api_contract.md, 5): слишком длинное описание отклоняется."""
    with pytest.raises(ValidationError, match="не должна превышать"):
        ProductCardRequest(description="а" * (MAX_TEXT_LENGTH + 1))


def test_product_card_request_soft_limit_counts_title_and_description() -> None:
    """Лимит считается по сумме title и description, а не по одному полю."""
    half = MAX_TEXT_LENGTH // 2 + 1
    payload = {"title": "а" * half, "description": "б" * half}

    with pytest.raises(ValidationError, match="не должна превышать"):
        ProductCardRequest(**payload)


def test_error_code_is_machine_readable() -> None:
    """ErrorCode — стабильные строковые коды для градации ошибок клиентом."""
    assert ErrorCode.NOT_FOUND.value == "not_found"
    assert ErrorCode.VALIDATION_ERROR.value == "validation_error"
    assert ErrorCode.RATE_LIMITED.value == "rate_limited"
    assert ErrorCode.INTERNAL_ERROR.value == "internal_error"


def test_batch_extract_request_defaults() -> None:
    request = BatchExtractRequest(items=[ProductCardRequest(title="Товар")])

    assert request.return_sources is True
    assert request.return_raw_values is True
    assert request.threshold_override is None


def test_batch_extract_request_rejects_empty_items() -> None:
    with pytest.raises(ValidationError):
        BatchExtractRequest(items=[])


def test_batch_extract_request_rejects_too_many_items() -> None:
    items = [ProductCardRequest(title=f"Товар {i}") for i in range(MAX_BATCH_SIZE + 1)]

    with pytest.raises(ValidationError):
        BatchExtractRequest(items=items)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("batch_size", 0),
        ("batch_size", MAX_BATCH_SIZE + 1),
        ("threshold_override", -0.1),
        ("threshold_override", 1.1),
    ],
)
def test_batch_extract_request_rejects_out_of_range(field: str, value: float) -> None:
    payload = {"items": [ProductCardRequest(title="Товар")], field: value}

    with pytest.raises(ValidationError):
        BatchExtractRequest(**payload)


def test_batch_extract_response_round_trip() -> None:
    result = ExtractionResult(
        product_id="sm-001",
        status=ExtractionStatus.OK,
        needs_review=False,
        pipeline_version="0.1.0",
        attributes=[
            AttributeCandidate(
                attribute_code="brand",
                raw_value="Samsung",
                normalized_value="Samsung",
                confidence=0.98,
                extraction_method=ExtractionMethod.RULE,
                is_confirmed_in_text=True,
            )
        ],
    )
    response = BatchExtractResponse(
        batch_id="batch-1",
        total=1,
        ok=1,
        low_confidence=0,
        errors=0,
        results=[result],
        processing_time_ms_total=42,
    )

    payload = response.model_dump()
    assert payload["batch_id"] == "batch-1"
    assert payload["results"][0]["attributes"][0]["attribute_code"] == "brand"


def test_batch_extract_response_persisted_defaults_to_true() -> None:
    """persisted по умолчанию True: поле выставляет сервер (api_contract.md, 3.5)."""
    response = BatchExtractResponse(total=0, ok=0, low_confidence=0, errors=0)

    assert response.persisted is True

    response.persisted = False
    assert response.model_dump()["persisted"] is False


def test_batch_summary_round_trip() -> None:
    """Сводка истории несёт id, время и счётчики; threshold опционален."""
    summary = BatchSummary(
        batch_id="b-1",
        created_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        total=2,
        ok=1,
        low_confidence=1,
        errors=0,
    )

    payload = summary.model_dump()
    assert payload["batch_id"] == "b-1"
    assert payload["created_at"].tzinfo is not None
    assert payload["total"] == 2
    assert summary.threshold is None


def test_batch_summary_requires_created_at() -> None:
    """Время создания обязательно: сервер всегда назначает его при записи."""
    with pytest.raises(ValidationError):
        BatchSummary(batch_id="b-1", total=1, ok=1, low_confidence=0, errors=0)


def test_batch_list_response_defaults() -> None:
    listing = BatchListResponse(items=[], total=0)

    assert listing.items == []
    assert listing.total == 0


def test_stored_batch_response_keeps_cards_and_response() -> None:
    """Сохранённый батч несёт исходные карточки и полный ответ; cards опц."""
    stored = StoredBatchResponse(
        batch_id="b-1",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        threshold=0.8,
        cards=[ProductCardRequest(title="Кофемолка")],
        response=BatchExtractResponse(total=1, ok=1, low_confidence=0, errors=0),
    )

    assert stored.cards[0].title == "Кофемолка"
    assert stored.response.persisted is True

    without_cards = StoredBatchResponse(
        batch_id="b-2",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        response=BatchExtractResponse(total=1, ok=1, low_confidence=0, errors=0),
    )
    assert without_cards.cards == []
    assert without_cards.threshold is None


def test_health_response_status_is_enum() -> None:
    health = HealthResponse(
        status=HealthStatus.DEGRADED,
        version="1.0.0",
        pipeline_version="0.1.0",
        models_loaded=["rule_engine"],
        uptime_seconds=123,
        cache_enabled=True,
    )

    assert health.status == "degraded"
    assert health.model_dump()["status"] == "degraded"


def test_health_response_defaults() -> None:
    health = HealthResponse(status=HealthStatus.OK, version="1.0.0", pipeline_version="0.1.0")

    assert health.models_loaded == []
    assert health.uptime_seconds is None
    assert health.cache_enabled is False


def test_error_response_optional_fields() -> None:
    error = ErrorResponse(detail="Плохой запрос")
    assert error.code is None
    assert error.errors is None

    error_with_details = ErrorResponse(
        detail="Ошибка валидации",
        code="validation_error",
        errors=[ErrorDetail(loc=["body", "items", 0], msg="empty", type="value_error")],
    )
    assert error_with_details.errors[0].loc == ["body", "items", 0]

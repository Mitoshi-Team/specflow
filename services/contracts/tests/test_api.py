import pytest
from pydantic import ValidationError

from specflow_contracts.api import (
    BatchExtractRequest,
    BatchExtractResponse,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    ProductCardRequest,
)
from specflow_contracts.constants import MAX_BATCH_SIZE
from specflow_contracts.domain import AttributeCandidate, ExtractionResult
from specflow_contracts.enums import (
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

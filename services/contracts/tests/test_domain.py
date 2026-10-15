import pytest
from pydantic import ValidationError

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
    ExtractionMethod,
    ExtractionStatus,
    SpanField,
)


def test_product_card_raw_text_collects_present_fields() -> None:
    card = ProductCard(
        title="Смартфон Samsung",
        description="Экран 6.7 дюйма",
        seller_attributes={"color": "чёрный"},
    )

    raw_text = card.raw_text
    assert "Смартфон Samsung" in raw_text
    assert "Экран 6.7 дюйма" in raw_text
    assert "чёрный" in raw_text


def test_product_card_raw_text_skips_empty_fields() -> None:
    card = ProductCard(product_id="sm-001")

    assert card.raw_text == ""
    assert card.has_text_content() is False


def test_product_card_accepts_list_seller_attributes() -> None:
    card = ProductCard(seller_attributes=[{"code": "color", "value": "чёрный"}])

    assert card.has_text_content() is True
    assert "color" in card.raw_text


def test_product_card_has_text_content_ignores_blank_title() -> None:
    card = ProductCard(title="   ", description="Описание")

    assert card.has_text_content() is True


def test_span_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        Span(field="image", text="x")


def test_span_accepts_valid_field_and_offsets() -> None:
    span = Span(field=SpanField.TITLE, text="Samsung", start=0, end=7)

    assert span.field == SpanField.TITLE
    assert span.start == 0
    assert span.end == 7


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_attribute_candidate_rejects_confidence_out_of_range(confidence: float) -> None:
    with pytest.raises(ValidationError):
        AttributeCandidate(
            attribute_code="brand",
            raw_value="Samsung",
            normalized_value="Samsung",
            confidence=confidence,
            extraction_method=ExtractionMethod.RULE,
            is_confirmed_in_text=True,
        )


def test_attribute_candidate_accepts_boundary_confidence() -> None:
    candidate = AttributeCandidate(
        attribute_code="brand",
        raw_value="samsung",
        normalized_value="Samsung",
        confidence=1.0,
        extraction_method=ExtractionMethod.DICT,
        is_confirmed_in_text=True,
        source_spans=[Span(field=SpanField.TITLE, text="Samsung")],
    )

    assert candidate.confidence == 1.0
    assert candidate.source_spans[0].field == SpanField.TITLE


def test_extraction_result_serializes_enums_as_values() -> None:
    result = ExtractionResult(
        product_id="sm-001",
        status=ExtractionStatus.OK,
        needs_review=False,
        pipeline_version="0.1.0",
    )

    payload = result.model_dump()
    assert payload["status"] == "ok"
    assert payload["attributes"] == []


def test_category_schema_groups_required_and_optional_attributes() -> None:
    schema = CategorySchema(
        category="Смартфоны",
        schema_version="1.0.0",
        required_attributes=[
            Attribute(code="brand", value_type=AttributeValueType.STRING, is_required=True)
        ],
        optional_attributes=[
            Attribute(
                code="color",
                value_type=AttributeValueType.ENUM,
                vocab=["чёрный", "белый"],
            )
        ],
    )

    assert schema.required_attributes[0].code == "brand"
    assert schema.required_attributes[0].is_required is True
    assert schema.optional_attributes[0].vocab == ["чёрный", "белый"]


def test_category_schema_defaults_are_empty_lists() -> None:
    schema = CategorySchema(category="Ноутбуки", schema_version="1.0.0")

    assert schema.required_attributes == []
    assert schema.optional_attributes == []

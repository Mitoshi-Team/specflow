"""Тесты нормализации значений (Этап 6)."""

from __future__ import annotations

from attribute_extractor.constants import REVIEW_THRESHOLD
from attribute_extractor.normalization import ValueNormalizer
from attribute_extractor.references import (
    AttributeVocab,
    BrandVocab,
    ReferenceCatalog,
    UnitRule,
)
from specflow_contracts import (
    Attribute,
    AttributeCandidate,
    AttributeValueType,
    CategorySchema,
    ExtractionMethod,
)


def _candidate(
    value: str,
    *,
    code: str = "color",
    confidence: float = 0.9,
    features: dict[str, object] | None = None,
) -> AttributeCandidate:
    return AttributeCandidate(
        attribute_code=code,
        raw_value=value,
        normalized_value=value,
        confidence=confidence,
        extraction_method=ExtractionMethod.RULE,
        is_confirmed_in_text=True,
        features=features,
    )


def _attribute(
    code: str,
    value_type: AttributeValueType,
    *,
    unit: str | None = None,
) -> Attribute:
    return Attribute(code=code, value_type=value_type, unit=unit)


def _catalog_with(vocab: AttributeVocab | None = None) -> ReferenceCatalog:
    catalog = ReferenceCatalog()
    if vocab is not None:
        catalog.register_attribute_vocab(vocab)
    return catalog


def test_basic_normalization_spaces_quotes_and_dashes() -> None:
    """Базовая очистка: пробелы, кавычки и дефисы."""
    normalizer = ValueNormalizer()
    candidate = _candidate("  Чёрный   «мат» – глянец  ")
    result = normalizer.normalize(candidate, _attribute("color", AttributeValueType.STRING))
    assert result is not None
    assert result.normalized_value == 'Чёрный "мат" - глянец'


def test_unit_abbreviation_unification() -> None:
    """Сокращения единиц приводятся к канонической форме (гб → ГБ)."""
    normalizer = ValueNormalizer()
    result = normalizer.normalize(
        _candidate("256 гб", code="storage"),
        _attribute("storage", AttributeValueType.UNIT_VALUE, unit="ГБ"),
    )
    assert result is not None
    assert result.normalized_value == "256 ГБ"


def test_inch_symbol_and_decimal_format() -> None:
    """Дюймовый символ и разделитель числа приводятся к каноническому виду."""
    normalizer = ValueNormalizer()
    result = normalizer.normalize(
        _candidate('6.7"', code="screen_size"),
        _attribute("screen_size", AttributeValueType.UNIT_VALUE, unit="дюйм"),
    )
    assert result is not None
    assert result.normalized_value == "6,7 дюйм"


def test_battery_unit_unification() -> None:
    """мАч/mah нормализуются в мА·ч."""
    normalizer = ValueNormalizer()
    result = normalizer.normalize(
        _candidate("5000 mah", code="battery"),
        _attribute("battery", AttributeValueType.UNIT_VALUE, unit="мА·ч"),
    )
    assert result is not None
    assert result.normalized_value == "5000 мА·ч"


def test_number_trailing_zeros_are_stripped() -> None:
    """Лишние нули в дробной части отбрасываются."""
    normalizer = ValueNormalizer()
    result = normalizer.normalize(
        _candidate("6.70 дюйм", code="screen_size"),
        _attribute("screen_size", AttributeValueType.UNIT_VALUE, unit="дюйм"),
    )
    assert result is not None
    assert result.normalized_value == "6,7 дюйм"


def test_numeric_range_is_preserved() -> None:
    """Диапазон значений нормализуется с сохранением границ."""
    normalizer = ValueNormalizer()
    result = normalizer.normalize(
        _candidate("128–256 гб", code="storage"),
        _attribute("storage", AttributeValueType.UNIT_VALUE, unit="ГБ"),
    )
    assert result is not None
    assert result.normalized_value == "128-256 ГБ"


def test_number_value_type_formatting() -> None:
    """Числовые значения приводятся к единому формату."""
    normalizer = ValueNormalizer()
    attribute = _attribute("count", AttributeValueType.NUMBER)
    thousands = normalizer.normalize(_candidate("1 000", code="count"), attribute)
    decimal = normalizer.normalize(_candidate("6.70", code="count"), attribute)
    assert thousands is not None
    assert decimal is not None
    assert thousands.normalized_value == "1000"
    assert decimal.normalized_value == "6,7"


def test_enum_canonical_value() -> None:
    """Enum-значение приводится к каноническому из vocab."""
    vocab = AttributeVocab(attribute_code="color", canonical_values=["Чёрный", "Белый"])
    normalizer = ValueNormalizer(_catalog_with(vocab))
    result = normalizer.normalize(
        _candidate("чёрный", code="color"), _attribute("color", AttributeValueType.ENUM)
    )
    assert result is not None
    assert result.normalized_value == "Чёрный"


def test_enum_synonym_value() -> None:
    """Enum-значение маппится через synonyms_map."""
    vocab = AttributeVocab(
        attribute_code="color",
        canonical_values=["Чёрный"],
        synonyms_map={"black": "Чёрный"},
    )
    normalizer = ValueNormalizer(_catalog_with(vocab))
    result = normalizer.normalize(
        _candidate("black", code="color"), _attribute("color", AttributeValueType.ENUM)
    )
    assert result is not None
    assert result.normalized_value == "Чёрный"


def test_enum_out_of_vocab_caps_confidence_to_review_threshold() -> None:
    """Вне словаря без strict: значение сохраняется, confidence → REVIEW_THRESHOLD.

    Этап 6 (спека): неуспех маппинга через synonyms_map даёт ``low_confidence``
    по порогам Этапа 10 — кандидат попадает в полосу
    ``REVIEW_THRESHOLD <= confidence < AUTO_THRESHOLD``.
    """
    vocab = AttributeVocab(attribute_code="color", canonical_values=["Чёрный"])
    normalizer = ValueNormalizer(_catalog_with(vocab), enum_strict=False)
    result = normalizer.normalize(
        _candidate("красный", code="color"), _attribute("color", AttributeValueType.ENUM)
    )
    assert result is not None
    assert result.normalized_value == "красный"
    assert REVIEW_THRESHOLD <= result.confidence < 0.80
    assert result.confidence == REVIEW_THRESHOLD
    assert result.features is None


def test_enum_out_of_vocab_keeps_already_low_confidence() -> None:
    """Уже низкая уверенность не повышается до порога review."""
    vocab = AttributeVocab(attribute_code="color", canonical_values=["Чёрный"])
    normalizer = ValueNormalizer(_catalog_with(vocab), enum_strict=False)
    result = normalizer.normalize(
        _candidate("красный", code="color", confidence=0.45),
        _attribute("color", AttributeValueType.ENUM),
    )
    assert result is not None
    assert result.confidence == 0.45


def test_enum_mapped_value_keeps_confidence() -> None:
    """Успешный маппинг (vocab/synonyms_map) не снижает уверенность."""
    vocab = AttributeVocab(
        attribute_code="color",
        canonical_values=["Чёрный"],
        synonyms_map={"black": "Чёрный"},
    )
    normalizer = ValueNormalizer(_catalog_with(vocab), enum_strict=False)
    result = normalizer.normalize(
        _candidate("black", code="color"), _attribute("color", AttributeValueType.ENUM)
    )
    assert result is not None
    assert result.normalized_value == "Чёрный"
    assert result.confidence == 0.9


def test_enum_out_of_vocab_dropped_when_strict() -> None:
    """Вне словаря при strict: кандидат отбрасывается."""
    vocab = AttributeVocab(attribute_code="color", canonical_values=["Чёрный"])
    normalizer = ValueNormalizer(_catalog_with(vocab), enum_strict=True)
    result = normalizer.normalize(
        _candidate("красный", code="color"), _attribute("color", AttributeValueType.ENUM)
    )
    assert result is None


def test_enum_out_of_vocab_preserves_existing_features() -> None:
    """Неуспех маппинга не добавляет признаков: features кандидата сохраняются."""
    vocab = AttributeVocab(attribute_code="color", canonical_values=["Чёрный"])
    normalizer = ValueNormalizer(_catalog_with(vocab))
    result = normalizer.normalize(
        _candidate("красный", code="color", features={"conflict": True}),
        _attribute("color", AttributeValueType.ENUM),
    )
    assert result is not None
    assert result.confidence == REVIEW_THRESHOLD
    assert result.features == {"conflict": True}


def test_string_synonym_mapping() -> None:
    """Строковые значения маппятся через synonyms_map справочника."""
    vocab = AttributeVocab(
        attribute_code="material",
        synonyms_map={"пластик": "Пластик"},
    )
    normalizer = ValueNormalizer(_catalog_with(vocab))
    result = normalizer.normalize(
        _candidate("пластик", code="material"),
        _attribute("material", AttributeValueType.STRING),
    )
    assert result is not None
    assert result.normalized_value == "Пластик"


def test_brand_canonicalization() -> None:
    """Бренды приводятся к каноническому имени из BrandVocab."""
    catalog = ReferenceCatalog()
    catalog.set_brand_vocab(BrandVocab(names=["Samsung", "Apple"]))
    normalizer = ValueNormalizer(catalog)
    result = normalizer.normalize(
        _candidate("samsung", code="brand"), _attribute("brand", AttributeValueType.STRING)
    )
    assert result is not None
    assert result.normalized_value == "Samsung"


def test_title_case_optional() -> None:
    """Title Case применяется только при включённой опции."""
    attribute = _attribute("material", AttributeValueType.STRING)
    assert (
        ValueNormalizer().normalize(_candidate("matte black"), attribute).normalized_value
        == "matte black"
    )
    assert (
        ValueNormalizer(title_case_enabled=True)
        .normalize(_candidate("matte black"), attribute)
        .normalized_value
        == "Matte Black"
    )


def test_unit_conversion_enabled() -> None:
    """При включённой конверсии единица приводится к канонической схемы."""
    catalog = ReferenceCatalog()
    catalog.register_unit_rule(
        UnitRule(attribute_code="ram", to_unit="ГБ", conversions={"МБ": 1 / 1024})
    )
    normalizer = ValueNormalizer(catalog, unit_conversion_enabled=True)
    result = normalizer.normalize(
        _candidate("1024 МБ", code="ram"),
        _attribute("ram", AttributeValueType.UNIT_VALUE, unit="ГБ"),
    )
    assert result is not None
    assert result.normalized_value == "1 ГБ"


def test_unit_conversion_disabled() -> None:
    """При выключенной конверсии единица только унифицируется."""
    catalog = ReferenceCatalog()
    catalog.register_unit_rule(
        UnitRule(attribute_code="ram", to_unit="ГБ", conversions={"МБ": 1 / 1024})
    )
    normalizer = ValueNormalizer(catalog, unit_conversion_enabled=False)
    result = normalizer.normalize(
        _candidate("1024 МБ", code="ram"),
        _attribute("ram", AttributeValueType.UNIT_VALUE, unit="ГБ"),
    )
    assert result is not None
    assert result.normalized_value == "1024 МБ"


def test_raw_value_is_preserved() -> None:
    """Исходное значение raw_value не меняется."""
    normalizer = ValueNormalizer()
    result = normalizer.normalize(
        _candidate("256 гб", code="storage"),
        _attribute("storage", AttributeValueType.UNIT_VALUE, unit="ГБ"),
    )
    assert result is not None
    assert result.raw_value == "256 гб"


def test_normalize_all_uses_schema_and_drops_strict() -> None:
    """normalize_all берёт типы из схемы и отбрасывает непрошедшие strict."""
    vocab = AttributeVocab(attribute_code="color", canonical_values=["Чёрный"])
    catalog = _catalog_with(vocab)
    normalizer = ValueNormalizer(catalog, enum_strict=True)
    schema = CategorySchema(
        category="smartphone",
        schema_version="1.0.0",
        required_attributes=[
            _attribute("color", AttributeValueType.ENUM),
            _attribute("storage", AttributeValueType.UNIT_VALUE, unit="ГБ"),
        ],
    )
    candidates = [
        _candidate("красный", code="color"),
        _candidate("256 гб", code="storage"),
    ]
    result = normalizer.normalize_all(candidates, schema)
    assert len(result) == 1
    assert result[0].attribute_code == "storage"
    assert result[0].normalized_value == "256 ГБ"

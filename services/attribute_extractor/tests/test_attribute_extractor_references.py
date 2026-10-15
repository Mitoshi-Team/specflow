"""Тесты справочников (AttributeVocab, UnitRule, BrandVocab, ReferenceCatalog)."""

from __future__ import annotations

from attribute_extractor.constants import DEFAULT_VOCAB_VERSION
from attribute_extractor.references import (
    AttributeVocab,
    BrandVocab,
    ReferenceCatalog,
    UnitRule,
    build_default_catalog,
)


def test_attribute_vocab_resolves_canonical_case_insensitive() -> None:
    """Каноническое значение сопоставляется без учёта регистра."""
    vocab = AttributeVocab(attribute_code="color", canonical_values=["Чёрный", "Белый"])
    assert vocab.resolve("чёрный") == "Чёрный"
    assert vocab.resolve("БЕЛЫЙ") == "Белый"


def test_attribute_vocab_resolves_synonym() -> None:
    """Синоним маппится в каноническое значение без учёта регистра."""
    vocab = AttributeVocab(
        attribute_code="color",
        canonical_values=["Чёрный"],
        synonyms_map={"black": "Чёрный"},
    )
    assert vocab.resolve("Black") == "Чёрный"


def test_attribute_vocab_unknown_and_empty_return_none() -> None:
    """Неизвестное и пустое значение не сопоставляются."""
    vocab = AttributeVocab(attribute_code="color", canonical_values=["Чёрный"])
    assert vocab.resolve("красный") is None
    assert vocab.resolve("  ") is None


def test_brand_vocab_resolves_name_and_alias() -> None:
    """Бренд сопоставляется по каноническому имени и алиасу."""
    vocab = BrandVocab(
        names=["Samsung", "Apple"],
        aliases={"sams": "Samsung"},
        stopwords=["brand"],
    )
    assert vocab.resolve("apple") == "Apple"
    assert vocab.resolve("SAMS") == "Samsung"


def test_brand_vocab_stopword_and_unknown_return_none() -> None:
    """Стоп-слова и неизвестные значения не сопоставляются."""
    vocab = BrandVocab(names=["Samsung"], stopwords=["brand"])
    assert vocab.resolve("brand") is None
    assert vocab.resolve("Nokia") is None


def test_reference_catalog_registers_and_returns() -> None:
    """Каталог возвращает зарегистрированные справочники."""
    catalog = ReferenceCatalog(version="2.0.0")
    vocab = AttributeVocab(attribute_code="color", canonical_values=["Чёрный"])
    rule = UnitRule(attribute_code="ram", to_unit="ГБ", conversions={"МБ": 0.001})
    brand = BrandVocab(names=["Samsung"])
    catalog.register_attribute_vocab(vocab)
    catalog.register_unit_rule(rule)
    catalog.set_brand_vocab(brand)

    assert catalog.version == "2.0.0"
    assert catalog.attribute_vocab("color") is vocab
    assert catalog.unit_rule("ram") is rule
    assert catalog.brand_vocab is brand


def test_reference_catalog_missing_returns_none() -> None:
    """Отсутствующие справочники возвращают ``None``."""
    catalog = ReferenceCatalog()
    assert catalog.attribute_vocab("color") is None
    assert catalog.unit_rule("ram") is None
    assert catalog.brand_vocab is None


def test_build_default_catalog_is_empty_with_default_version() -> None:
    """Каталог по умолчанию пуст и использует версию по умолчанию."""
    catalog = build_default_catalog()
    assert catalog.version == DEFAULT_VOCAB_VERSION
    assert catalog.brand_vocab is None

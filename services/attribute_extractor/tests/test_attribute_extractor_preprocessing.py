"""Тесты препроцессинга карточки (Этап 0)."""

from __future__ import annotations

import pytest

from attribute_extractor.constants import (
    GENERIC_CATEGORY,
    GENERIC_SCHEMA_VERSION,
    LANGUAGE_EN,
    LANGUAGE_MIXED,
    LANGUAGE_RU,
    LANGUAGE_UNKNOWN,
)
from attribute_extractor.preprocessing import (
    CardPreprocessor,
    SchemaRegistry,
    detect_language,
    generic_schema,
    normalize_text,
    tokenize,
)
from specflow_contracts import Attribute, AttributeValueType, CategorySchema, ProductCard


def _schema(
    category: str,
    category_id: str | None = None,
    version: str = "1.0.0",
) -> CategorySchema:
    return CategorySchema(
        category=category,
        category_id=category_id,
        schema_version=version,
        required_attributes=[Attribute(code="color", value_type=AttributeValueType.STRING)],
    )


def test_normalize_collapses_whitespace_and_line_breaks() -> None:
    """Множественные пробелы, переносы и табуляции схлопываются в один пробел."""
    raw = "  Ламинат   32\tкласс \n 1,5 м²  "
    assert normalize_text(raw) == "Ламинат 32 класс 1,5 м²"


def test_normalize_handles_crlf_and_nbsp() -> None:
    """CRLF и неразрывный пробел нормализуются в обычный пробел."""
    assert normalize_text("a\r\nb\u00a0c") == "a b c"


def test_normalize_quotes() -> None:
    """Типографские кавычки и апострофы приводятся к ASCII."""
    assert normalize_text("«Цвет: чёрный»") == '"Цвет: чёрный"'
    assert normalize_text("it’s „Dell”") == 'it\'s "Dell"'


def test_normalize_removes_junk_chars_by_default() -> None:
    """Невидимые символы удаляются при нормализации по умолчанию."""
    assert normalize_text("Теле\u200bви\u200eзор\ufeff") == "Телевизор"


def test_normalize_keeps_junk_chars_when_disabled() -> None:
    """При remove_junk_chars=False мусорные символы сохраняются."""
    text = "Теле\u200bвизор"
    assert normalize_text(text, remove_junk_chars=False) == "Теле\u200bвизор"


def test_normalize_preserves_case() -> None:
    """Нормализация не меняет регистр текста."""
    assert normalize_text("Цвет ЧЁрный") == "Цвет ЧЁрный"


def test_normalize_empty() -> None:
    """Пустой ввод даёт пустую строку."""
    assert normalize_text("") == ""
    assert normalize_text("   \n\t ") == ""


def test_tokenize_splits_on_whitespace() -> None:
    """Токенизация разбивает текст по пробелам."""
    assert tokenize("Ламинат 32 класс") == ["Ламинат", "32", "класс"]
    assert tokenize("") == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Привет мир", LANGUAGE_RU),
        ("Hello world", LANGUAGE_EN),
        ("Телефон iPhone 15 Pro", LANGUAGE_MIXED),
        ("12345 - 678", LANGUAGE_UNKNOWN),
        ("", LANGUAGE_UNKNOWN),
    ],
)
def test_detect_language(text: str, expected: str) -> None:
    """Автоопределение языка по алфавиту текста."""
    assert detect_language(text) == expected


def test_detect_language_minority_below_share_is_majority() -> None:
    """Малая доля второго алфавита не делает текст смешанным."""
    text = "The quick brown fox jumps я"
    assert detect_language(text) == LANGUAGE_EN


def test_generic_schema_shape() -> None:
    """Generic-схема имеет пустые списки атрибутов и фиксированные метаданные."""
    schema = generic_schema()
    assert schema.category == GENERIC_CATEGORY
    assert schema.schema_version == GENERIC_SCHEMA_VERSION
    assert schema.required_attributes == []
    assert schema.optional_attributes == []


def test_preprocess_builds_raw_text_and_normalizes() -> None:
    """Препроцессинг собирает raw_text, нормализует и токенизирует текст."""
    card = ProductCard(title="  Ламинат   32 класс ", description="Толщина\n8 мм")
    result = CardPreprocessor().preprocess(card)
    assert result.raw_text == "  Ламинат   32 класс  Толщина\n8 мм"
    assert result.normalized_text == "Ламинат 32 класс Толщина 8 мм"
    assert result.tokens == ["Ламинат", "32", "класс", "Толщина", "8", "мм"]


def test_preprocess_includes_seller_attributes_in_raw_text() -> None:
    """Структурированные поля продавца попадают в raw_text."""
    card = ProductCard(title="Ламинат", seller_attributes={"цвет": "дуб"})
    result = CardPreprocessor().preprocess(card)
    assert "дуб" in result.raw_text
    assert "дуб" in result.normalized_text


def test_preprocess_detects_language() -> None:
    """Язык определяется из текста, если не задан в карточке."""
    card = ProductCard(title="Телефон iPhone 15 Pro")
    assert CardPreprocessor().preprocess(card).language == LANGUAGE_MIXED


def test_preprocess_respects_explicit_language() -> None:
    """Явно указанный в карточке язык имеет приоритет над автоопределением."""
    card = ProductCard(title="Hello world", language="ru")
    assert CardPreprocessor().preprocess(card).language == LANGUAGE_RU


def test_preprocess_empty_card() -> None:
    """Карточка без текста обрабатывается без ошибок."""
    card = ProductCard()
    result = CardPreprocessor().preprocess(card)
    assert result.raw_text == ""
    assert result.normalized_text == ""
    assert result.tokens == []
    assert result.language == LANGUAGE_UNKNOWN
    assert result.category_schema.category == GENERIC_CATEGORY


def test_schema_resolution_by_id() -> None:
    """Схема резолвится по category_id."""
    registry = SchemaRegistry([_schema("Напольные покрытия", category_id="flooring")])
    card = ProductCard(title="Ламинат", category_id="flooring")
    assert registry.resolve(card).category_id == "flooring"


def test_schema_resolution_by_name_case_insensitive() -> None:
    """Схема резолвится по названию без учёта регистра и пробелов."""
    registry = SchemaRegistry([_schema("Напольные покрытия", category_id="flooring")])
    card = ProductCard(title="Ламинат", category_name="  напольные ПОКРЫТИЯ ")
    assert registry.resolve(card).category == "Напольные покрытия"


def test_schema_resolution_prefers_id_over_name() -> None:
    """category_id имеет приоритет над category_name."""
    by_id = _schema("Категория по ID", category_id="flooring")
    by_name = _schema("Напольные покрытия", category_id="other")
    registry = SchemaRegistry([by_id, by_name])
    card = ProductCard(category_id="flooring", category_name="Напольные покрытия")
    assert registry.resolve(card) is by_id


def test_schema_resolution_fallback_to_generic() -> None:
    """При неизвестной категории возвращается generic-схема с сохранением полей карточки."""
    registry = SchemaRegistry([_schema("Напольные покрытия", category_id="flooring")])
    card = ProductCard(category_id="unknown-id", category_name="Неизвестно")
    result = CardPreprocessor(registry).preprocess(card)
    assert result.category_schema.category == GENERIC_CATEGORY
    assert result.card.category_id == "unknown-id"
    assert result.card.category_name == "Неизвестно"


def test_schema_registry_get_unknown_returns_none() -> None:
    """get для отсутствующей категории возвращает None."""
    registry = SchemaRegistry()
    assert registry.get("missing", "missing") is None


def test_preprocessor_respects_remove_junk_flag() -> None:
    """Флаг remove_junk_chars прокидывается в нормализацию."""
    card = ProductCard(title="Теле\u200bвизор")
    kept = CardPreprocessor(remove_junk_chars=False).preprocess(card)
    removed = CardPreprocessor().preprocess(card)
    assert kept.normalized_text == "Теле\u200bвизор"
    assert removed.normalized_text == "Телевизор"

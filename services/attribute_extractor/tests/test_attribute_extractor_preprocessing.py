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
    strip_service_noise,
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


def test_normalize_strips_html_tags() -> None:
    """Инлайновые HTML-теги снимаются, содержимое сохраняется."""
    assert normalize_text("Кофемашина <b>De'Longhi</b> Magnifica") == (
        "Кофемашина De'Longhi Magnifica"
    )


def test_normalize_replaces_block_tags_with_space() -> None:
    """Теги-разделители дают пробел, чтобы слова не склеивались."""
    assert normalize_text("Экран<br>6.7 дюйма") == "Экран 6.7 дюйма"
    assert normalize_text("<p>Цвет: чёрный</p><p>Материал: дуб</p>") == "Цвет: чёрный Материал: дуб"


def test_normalize_strips_self_closing_comment_and_doctype() -> None:
    """Самозакрывающиеся теги, комментарии и doctype удаляются."""
    text = '<!DOCTYPE html><!-- шаблон --><img src="x.png" /><span>Холодильник</span>'
    assert normalize_text(text) == "Холодильник"


def test_normalize_keeps_text_that_looks_like_comparison() -> None:
    """Символьные сравнения без буквы после ``<`` не считаются разметкой."""
    assert normalize_text("Напряжение 5 < 7 В") == "Напряжение 5 < 7 В"
    assert normalize_text("Фильтр a < b > c подходит") == "Фильтр a < b > c подходит"


def test_normalize_unescapes_html_entities() -> None:
    """HTML-сущности декодируются, включая экранированную разметку."""
    assert normalize_text("Кофе &amp; чай&nbsp;100%") == "Кофе & чай 100%"
    assert normalize_text("Цена &lt; 1000 ₽") == "Цена < 1000 ₽"
    assert normalize_text("&lt;strong&gt;Блендер&lt;/strong&gt;") == "Блендер"


def test_normalize_keeps_html_when_disabled() -> None:
    """При remove_html_tags=False теги и сущности сохраняются."""
    assert normalize_text("Экран<br>6.7", remove_html_tags=False) == "Экран<br>6.7"
    assert normalize_text("Кофе &amp; чай", remove_html_tags=False) == "Кофе &amp; чай"


def test_tokenize_splits_on_whitespace() -> None:
    """Токенизация разбивает текст по пробелам."""
    assert tokenize("Ламинат 32 класс") == ["Ламинат", "32", "класс"]
    assert tokenize("") == []


@pytest.mark.parametrize(
    "phrase",
    [
        "Подборки",
        "Потратить бонусы",
        "Гарантия предоставляется",
        "ЗД для отчета BI/BO",
        "Лучшие товары из Китая",
    ],
)
def test_strip_service_noise_removes_standalone_insertion(phrase: str) -> None:
    """Служебная вставка-фраза удаляется вместе со своим предложением."""
    assert strip_service_noise(f"Смартфон Samsung. {phrase}.") == "Смартфон Samsung."


def test_strip_service_noise_removes_seller_field_with_value() -> None:
    """Метка «Продавец» вырезается вместе со значением до конца предложения."""
    text = "Продавец: ИП Иванов. Смартфон Samsung."
    assert strip_service_noise(text) == "Смартфон Samsung."


def test_strip_service_noise_keeps_meaningful_sentence() -> None:
    """Если после удаления фразы остаётся содержание, предложение сохраняется."""
    assert strip_service_noise("Подборки диагоналей актуальны") == "диагоналей актуальны"


def test_strip_service_noise_empty() -> None:
    """Пустой ввод не меняется."""
    assert strip_service_noise("") == ""


def test_strip_service_noise_keeps_decimals_and_abbreviations() -> None:
    """Десятичные точки и сокращения не разрываются при чистке."""
    text = "Диагональ 6.7, доставка и т.д. Подборки."
    assert strip_service_noise(text) == "Диагональ 6.7, доставка и т.д."


def test_normalize_removes_service_noise_by_default() -> None:
    """Нормализация по умолчанию удаляет служебные вставки и водяные знаки."""
    raw = "Смартфон Samsung. Потратить бонусы. Гарантия предоставляется."
    assert normalize_text(raw) == "Смартфон Samsung."


def test_normalize_keeps_service_noise_when_disabled() -> None:
    """При remove_service_noise=False служебные вставки сохраняются."""
    raw = "Смартфон Samsung. Потратить бонусы."
    assert normalize_text(raw, remove_service_noise=False) == (
        "Смартфон Samsung. Потратить бонусы."
    )


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


def test_preprocess_strips_html_from_title_and_description() -> None:
    """Очистка снимает HTML из title/description, raw_text остаётся сырым."""
    card = ProductCard(
        title="<b>Ламинат</b> 32 класс",
        description="Толщина<br>8 мм &amp; упаковка",
    )
    result = CardPreprocessor().preprocess(card)
    assert result.raw_text == "<b>Ламинат</b> 32 класс Толщина<br>8 мм &amp; упаковка"
    assert result.normalized_text == "Ламинат 32 класс Толщина 8 мм & упаковка"
    assert result.tokens == ["Ламинат", "32", "класс", "Толщина", "8", "мм", "&", "упаковка"]


def test_preprocessor_respects_remove_html_flag() -> None:
    """Флаг remove_html_tags прокидывается в нормализацию."""
    card = ProductCard(title="Экран<br>6.7 дюйма")
    kept = CardPreprocessor(remove_html_tags=False).preprocess(card)
    removed = CardPreprocessor().preprocess(card)
    assert kept.normalized_text == "Экран<br>6.7 дюйма"
    assert removed.normalized_text == "Экран 6.7 дюйма"


def test_preprocessor_respects_remove_service_noise_flag() -> None:
    """Флаг remove_service_noise прокидывается в нормализацию, raw_text не меняется."""
    card = ProductCard(title="Смартфон Samsung. Продавец: ИП Иванов. Потратить бонусы")
    kept = CardPreprocessor(remove_service_noise=False).preprocess(card)
    removed = CardPreprocessor().preprocess(card)
    assert kept.normalized_text == "Смартфон Samsung. Продавец: ИП Иванов. Потратить бонусы"
    assert removed.normalized_text == "Смартфон Samsung."
    assert removed.raw_text == card.raw_text

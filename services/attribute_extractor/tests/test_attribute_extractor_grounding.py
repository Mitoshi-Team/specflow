"""Тесты проверки подтверждения кандидатов в тексте (Этап 5)."""

from __future__ import annotations

from attribute_extractor.grounding import GroundingValidator
from specflow_contracts import AttributeCandidate, ExtractionMethod, ProductCard, Span, SpanField


def _candidate(
    value: str = "black",
    *,
    code: str = "color",
    confirmed: bool = False,
    spans: list[Span] | None = None,
    evidence: str | None = None,
) -> AttributeCandidate:
    return AttributeCandidate(
        attribute_code=code,
        raw_value=value,
        normalized_value=value,
        confidence=0.9,
        extraction_method=ExtractionMethod.RULE,
        is_confirmed_in_text=confirmed,
        source_spans=spans or [],
        evidence_text=evidence,
    )


def test_exact_evidence_substring_in_title() -> None:
    """Точное вхождение evidence_text в заголовок подтверждает кандидата."""
    validator = GroundingValidator()
    card = ProductCard(title="Смартфон Apple iPhone 15 Pro 256 ГБ")
    candidate = _candidate("256 ГБ", evidence="256 ГБ")
    assert validator.is_grounded(candidate, card) is True


def test_case_and_whitespace_insensitive_match() -> None:
    """Совпадение не зависит от регистра и лишних пробелов."""
    validator = GroundingValidator()
    card = ProductCard(description="Цвет:   ЧЁРНЫЙ")
    candidate = _candidate("чёрный", evidence="чёрный")
    assert validator.is_grounded(candidate, card) is True


def test_decimal_comma_matches_dot() -> None:
    """Десятичная запятая сопоставляется с точкой (6,7 ↔ 6.7)."""
    validator = GroundingValidator()
    card = ProductCard(title="Экран 6.7 дюйма, OLED")
    candidate = _candidate("6,7", evidence="6,7 дюйма")
    assert validator.is_grounded(candidate, card) is True


def test_unit_alias_cyrillic_latin() -> None:
    """Синонимы единиц сопоставляются (ГБ ↔ GB)."""
    validator = GroundingValidator()
    card = ProductCard(description="Встроенная память 256 GB")
    candidate = _candidate("256 ГБ", evidence="256 ГБ")
    assert validator.is_grounded(candidate, card) is True


def test_inch_symbol_matches_word() -> None:
    """Дюймовый символ сопоставляется со словом (6.7\" ↔ дюймов)."""
    validator = GroundingValidator()
    card = ProductCard(title='Диагональ 6.7"')
    candidate = _candidate("6.7 дюймов")
    assert validator.is_grounded(candidate, card) is True


def test_hyphenated_inch_adjective_is_grounded() -> None:
    """Форма «6.7-дюймовый» подтверждает значение «6,7 дюйм»."""
    validator = GroundingValidator()
    card = ProductCard(description="Большой 6.7-дюймовый дисплей")
    candidate = _candidate("6,7 дюйм", code="diagonal")
    assert validator.is_grounded(candidate, card) is True


def test_glued_inch_symbol_before_word_is_grounded() -> None:
    """Слипшаяся форма «14\"OLED» подтверждает значение «14 дюйм»."""
    validator = GroundingValidator()
    card = ProductCard(title='Ноутбук 14"OLED 1920x1200')
    candidate = _candidate("14 дюйм", code="diagonal")
    assert validator.is_grounded(candidate, card) is True


def test_slash_glued_model_token_is_grounded() -> None:
    """Модель находится, когда слэш склеил её с диагональю («F17/17,3"»)."""
    validator = GroundingValidator()
    card = ProductCard(title='Ноутбук ASUS TUF Gaming F17/17,3"/IPS/Core i7-13620H/16Гб')
    candidate = _candidate("TUF Gaming F17", code="model")
    assert validator.is_grounded(candidate, card) is True


def test_slash_glued_processor_token_is_grounded() -> None:
    """Процессор находится, когда слэш склеил его с памятью («i7-13620H/16Гб»)."""
    validator = GroundingValidator()
    card = ProductCard(title='Ноутбук ASUS TUF Gaming F17/17,3"/IPS/Core i7-13620H/16Гб')
    candidate = _candidate("Core i7-13620H", code="processor")
    assert validator.is_grounded(candidate, card) is True


def test_html_tag_glued_unit_is_grounded() -> None:
    """HTML-тег после единицы не мешает grounding («5088 мА*ч</b>»)."""
    validator = GroundingValidator()
    card = ProductCard(description="• <b>Аккумулятор 5088 мА*ч</b> Ресурс батареи")
    candidate = _candidate("5088 мА·ч", code="battery_capacity")
    assert validator.is_grounded(candidate, card) is True


def test_trailing_comma_does_not_break_token() -> None:
    """Запятая после слова не мешает grounding («серый, клавиатура»)."""
    validator = GroundingValidator()
    card = ProductCard(title='Ноутбук Echips Taganay 17.3" серый, клавиатура с подсветкой')
    candidate = _candidate("серый", code="color")
    assert validator.is_grounded(candidate, card) is True


def test_unicode_dash_inch_adjective_is_grounded() -> None:
    """Неразрывный дефис в «13,1‑дюймовым» подтверждает значение «13,1 дюйм»."""
    validator = GroundingValidator()
    card = ProductCard(description="Оснащён 13,1\u2011дюймовым IPS-экраном")
    candidate = _candidate("13,1 дюйм", code="diagonal")
    assert validator.is_grounded(candidate, card) is True


def test_underscore_glued_token_is_split() -> None:
    """Подчёркивания не мешают найти модель («TDT3778_WI_E_CIS»)."""
    validator = GroundingValidator()
    card = ProductCard(title="Планшет TopDevice TDT3778_WI_E_CIS")
    candidate = _candidate("TDT3778", code="model")
    assert validator.is_grounded(candidate, card) is True


def test_html_entity_nbsp_is_grounded() -> None:
    """HTML-сущность «&nbsp;» не мешает grounding («10&nbsp;090 мА·ч»)."""
    validator = GroundingValidator()
    card = ProductCard(description="аккумулятор ёмкостью 10&nbsp;090&nbsp;мА·ч")
    candidate = _candidate("10 090 мА·ч", code="battery_capacity")
    assert validator.is_grounded(candidate, card) is True


def test_seller_attributes_noise_marker_keeps_following_values() -> None:
    """Маркер «Продавец» не съедает значения следующих атрибутов продавца."""
    validator = GroundingValidator()
    card = ProductCard(
        title="Смартфон Apple iPhone 17 Pro 256 ГБ",
        seller_attributes={
            "Продавец": "ИП Бирюзов Евгений Анатольевич",
            "Цвет": "синий",
        },
    )
    candidate = _candidate("синий", code="color")
    assert validator.is_grounded(candidate, card) is True


def test_battery_asterisk_variant_is_grounded() -> None:
    """Типографский вариант «мА*ч» сопоставляется с каноническим «мА·ч»."""
    validator = GroundingValidator()
    card = ProductCard(description="Аккумулятор емкостью 5000 мА*ч")
    candidate = _candidate("5000 мА·ч", code="battery_capacity")
    assert validator.is_grounded(candidate, card) is True


def test_missing_value_is_not_grounded() -> None:
    """Отсутствующее в тексте значение не подтверждается."""
    validator = GroundingValidator()
    card = ProductCard(title="Смартфон Apple iPhone 15 Pro")
    candidate = _candidate("512 ГБ", code="storage")
    assert validator.is_grounded(candidate, card) is False


def test_token_fallback_without_evidence() -> None:
    """Без evidence_text подтверждение ищется по токенам значения."""
    validator = GroundingValidator()
    card = ProductCard(description="Оперативная память 8 ГБ LPDDR5")
    candidate = _candidate("8 ГБ", code="ram")
    assert validator.is_grounded(candidate, card) is True


def test_token_match_is_exact() -> None:
    """Токены сопоставляются точно: 8 не подтверждается текстом 18."""
    validator = GroundingValidator()
    card = ProductCard(description="Встроенная память 18 ГБ")
    candidate = _candidate("8", code="ram")
    assert validator.is_grounded(candidate, card) is False


def test_seller_attributes_are_searchable() -> None:
    """Значения ищутся и в seller_attributes."""
    validator = GroundingValidator()
    card = ProductCard(seller_attributes={"Память": "128 ГБ"})
    candidate = _candidate("128 ГБ", evidence="128 ГБ")
    assert validator.is_grounded(candidate, card) is True


def test_seller_attributes_token_fallback() -> None:
    """Без evidence значения словаря находятся по токенам (repr-пунктуация не мешает)."""
    validator = GroundingValidator()
    card = ProductCard(seller_attributes={"Ёмкость аккумулятора": "5000 мА·ч"})
    candidate = _candidate("5000 мА·ч", code="battery_capacity")
    assert validator.is_grounded(candidate, card) is True


def test_seller_attributes_list_is_searchable() -> None:
    """Список seller_attributes тоже участвует в поиске."""
    validator = GroundingValidator()
    card = ProductCard(seller_attributes=["Цвет: синий", "Память: 128 ГБ"])
    candidate = _candidate("128 ГБ", code="storage")
    assert validator.is_grounded(candidate, card) is True


def test_filter_drops_ungrounded_and_sets_confirmation() -> None:
    """Hard filter отбрасывает неподтверждённые и помечает подтверждённые."""
    validator = GroundingValidator()
    card = ProductCard(title="Телефон с экраном 6.7 дюйма")
    grounded = _candidate("6.7", evidence="6.7")
    ungrounded = _candidate("512 ГБ", code="storage")
    result = validator.filter([grounded, ungrounded], card)
    assert len(result) == 1
    assert result[0].attribute_code == "color"
    assert result[0].is_confirmed_in_text is True


def test_filter_adds_span_when_absent() -> None:
    """Hard filter добавляет span найденного упоминания, если его не было."""
    validator = GroundingValidator()
    card = ProductCard(title="Смартфон 256 ГБ")
    result = validator.filter([_candidate("256 ГБ", evidence="256 ГБ")], card)
    assert len(result) == 1
    span = result[0].source_spans[0]
    assert span.field is SpanField.TITLE
    assert span.text == "256 ГБ"
    assert span.start == 9


def test_filter_keeps_existing_spans() -> None:
    """Существующие source_spans не перезаписываются."""
    validator = GroundingValidator()
    card = ProductCard(title="Смартфон 256 ГБ")
    span = Span(field=SpanField.TITLE, text="256 ГБ", start=0, end=6)
    result = validator.filter([_candidate("256 ГБ", spans=[span])], card)
    assert result[0].source_spans == [span]


def test_empty_card_text_is_not_grounded() -> None:
    """Карточка без текста не подтверждает кандидатов."""
    validator = GroundingValidator()
    candidate = _candidate("256 ГБ")
    assert validator.is_grounded(candidate, ProductCard()) is False

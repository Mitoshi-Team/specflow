"""Тесты RuleExtractor — детерминированные правила (Этап 3, §3.2 спеки)."""

from __future__ import annotations

import pytest

from attribute_extractor.constants import DEFAULT_DETERMINISTIC_CONFIDENCE
from attribute_extractor.extractors import RuleExtractor
from attribute_extractor.grounding import GroundingValidator
from attribute_extractor.references import BrandVocab
from specflow_contracts import (
    AttributeCandidate,
    CategorySchema,
    ExtractionMethod,
    ProductCard,
    SpanField,
)


def _schema() -> CategorySchema:
    return CategorySchema(category="smartphones", schema_version="1.0.0")


def _extract(card: ProductCard, extractor: RuleExtractor | None = None) -> list[AttributeCandidate]:
    return (extractor or RuleExtractor()).extract(card, _schema())


def _by_code(candidates: list[AttributeCandidate]) -> dict[str, AttributeCandidate]:
    return {candidate.attribute_code: candidate for candidate in candidates}


def _codes(candidates: list[AttributeCandidate]) -> list[str]:
    return [candidate.attribute_code for candidate in candidates]


def _assert_span_points_to_text(candidate: AttributeCandidate, original: str) -> None:
    assert len(candidate.source_spans) == 1
    span = candidate.source_spans[0]
    assert span.start is not None and span.end is not None
    assert original[span.start : span.end] == span.text


# --- Диагональ ---------------------------------------------------------------


def test_diagonal_word_unit() -> None:
    """«Экран 6,7 дюймов» → diagonal 6,7 дюйм со спаном в описании."""
    card = ProductCard(description="Экран 6,7 дюймов, AMOLED")
    candidate = _by_code(_extract(card))["diagonal"]
    assert candidate.normalized_value == "6,7 дюйм"
    assert candidate.raw_value == "6,7 дюймов"
    assert candidate.source_spans[0].field is SpanField.DESCRIPTION
    _assert_span_points_to_text(candidate, card.description)


def test_diagonal_inch_symbol() -> None:
    """Дюймовый символ после числа — диагональ («27"»)."""
    card = ProductCard(title='Монитор 27" IPS 2560x1440')
    candidate = _by_code(_extract(card))["diagonal"]
    assert candidate.normalized_value == "27 дюйм"


def test_diagonal_hyphenated_form() -> None:
    """Дефис между числом и единицей («6.7-дюймовый»), точка → каноническая запятая."""
    card = ProductCard(title="Смартфон 6.7-дюймовый, 128 ГБ")
    candidates = _extract(card)
    candidate = _by_code(candidates)["diagonal"]
    assert candidate.normalized_value == "6,7 дюйм"
    assert candidate.raw_value == "6.7-дюймовый"


# --- Ёмкость батареи ---------------------------------------------------------


@pytest.mark.parametrize(
    "fragment",
    ["Батарея 5000 мА·ч", "Батарея 5000 мАч", "Батарея 5000mAh"],
)
def test_battery_capacity_forms(fragment: str) -> None:
    """Все написания единицы (мА·ч/мАч/mAh) дают канон «5000 мА·ч»."""
    card = ProductCard(description=fragment)
    candidate = _by_code(_extract(card))["battery_capacity"]
    assert candidate.normalized_value == "5000 мА·ч"


def test_battery_range_is_skipped() -> None:
    """Диапазон продавца «3000-5000 мАч» не извлекается как одиночное значение."""
    card = ProductCard(description="Батарея 3000-5000 мАч, съемная")
    assert "battery_capacity" not in _by_code(_extract(card))


# --- Память: ОЗУ / накопитель / встроенный -----------------------------------


def test_memory_slash_pair_ram_and_storage() -> None:
    """«8/256 ГБ» → первый объём ОЗУ, второй — встроенный накопитель."""
    card = ProductCard(title="Смартфон Acme X 8/256 ГБ, чёрный")
    by_code = _by_code(_extract(card))
    assert "ram" in by_code and "storage" in by_code
    assert by_code["ram"].normalized_value == "8 ГБ"
    assert by_code["storage"].normalized_value == "256 ГБ"


def test_memory_slash_pair_ascii_units() -> None:
    """Английские сокращения пары («4/128GB») приводятся к ГБ."""
    card = ProductCard(title="realme C33 4/128GB Gold")
    by_code = _by_code(_extract(card))
    assert by_code["ram"].normalized_value == "4 ГБ"
    assert by_code["storage"].normalized_value == "128 ГБ"


def test_memory_single_defaults_to_storage() -> None:
    """Одиночное значение без ключевых слов — встроенный накопитель."""
    card = ProductCard(title="Samsung Galaxy S25 Ultra 512GB")
    by_code = _by_code(_extract(card))
    assert by_code["storage"].normalized_value == "512 ГБ"
    assert "ram" not in by_code


def test_memory_ram_by_keyword() -> None:
    """Слово «оператив» рядом со значением → ОЗУ."""
    card = ProductCard(description="Объём оперативной памяти 8 ГБ")
    by_code = _by_code(_extract(card))
    assert by_code["ram"].normalized_value == "8 ГБ"
    assert "storage" not in by_code


def test_memory_ozu_keyword() -> None:
    """Аббревиатура «ОЗУ» рядом со значением → ОЗУ."""
    card = ProductCard(description="ОЗУ 6 ГБ")
    by_code = _by_code(_extract(card))
    assert by_code["ram"].normalized_value == "6 ГБ"
    assert "storage" not in by_code


def test_memory_drive_by_keyword() -> None:
    """Ключевые слова накопителя («SSD») → drive."""
    card = ProductCard(description="Накопитель SSD 1 ТБ")
    by_code = _by_code(_extract(card))
    assert by_code["drive"].normalized_value == "1 ТБ"
    assert "storage" not in by_code


def test_memory_adjacent_pair_without_keywords() -> None:
    """Соседние значения без ключевых слов: первое — ОЗУ, второе — накопитель."""
    card = ProductCard(description="Память 8 ГБ ROM 256 ГБ")
    by_code = _by_code(_extract(card))
    assert by_code["ram"].normalized_value == "8 ГБ"
    assert by_code["storage"].normalized_value == "256 ГБ"


def test_memory_keyword_wins_over_adjacency() -> None:
    """Явное ключевое слово важнее эвристики соседства («SSD ... HDD ...”)."""
    card = ProductCard(description="SSD 1 ТБ, HDD 2 ТБ")
    drive_values = sorted(
        candidate.normalized_value
        for candidate in _extract(card)
        if candidate.attribute_code == "drive"
    )
    assert drive_values == ["1 ТБ", "2 ТБ"]


def test_memory_keyword_does_not_bleed_across_values() -> None:
    """Ключевое слово между значениями не отбирает метку у левого значения.

    «Оперативная память 4 ГБ, SSD 1 ТБ»: 4 ГБ — ОЗУ, 1 ТБ — накопитель;
    разрез «SSD» серединой окна не должен теряться или прилипать не туда.
    """
    card = ProductCard(description="Оперативная память 4 ГБ, SSD 1 ТБ")
    by_code = _by_code(_extract(card))
    assert by_code["ram"].normalized_value == "4 ГБ"
    assert by_code["drive"].normalized_value == "1 ТБ"
    assert "storage" not in by_code


def test_memory_range_is_skipped() -> None:
    """Диапазон «128-256 ГБ» не извлекается."""
    card = ProductCard(description="Память 128-256 ГБ на выбор")
    assert not {"ram", "storage", "drive"} & set(_codes(_extract(card)))


def test_memory_same_value_deduplicated_within_field() -> None:
    """Повторное упоминание того же значения в одном поле не дублируется."""
    card = ProductCard(description="Оперативная память 8 ГБ. ОЗУ 8 ГБ.")
    ram = [c for c in _extract(card) if c.attribute_code == "ram"]
    assert len(ram) == 1


def test_memory_same_value_kept_per_field() -> None:
    """Одно и то же значение в title и description — кандидаты на оба поля."""
    card = ProductCard(title="Смартфон 8 ГБ RAM", description="Оперативная память 8 ГБ")
    ram = [c for c in _extract(card) if c.attribute_code == "ram"]
    assert {c.source_spans[0].field for c in ram} == {SpanField.TITLE, SpanField.DESCRIPTION}


# --- Цвет --------------------------------------------------------------------


def test_color_template() -> None:
    """Шаблон «Цвет: чёрный» → канон «черный» (ё→е)."""
    card = ProductCard(description="Цвет: чёрный")
    candidate = _by_code(_extract(card))["color"]
    assert candidate.normalized_value == "черный"
    assert candidate.evidence_text == "чёрный"


def test_color_template_with_qualifier() -> None:
    """Уточняющее слово между «цвет» и значением («цвет корпуса: синий»)."""
    card = ProductCard(description="Цвет корпуса: синий")
    candidate = _by_code(_extract(card))["color"]
    assert candidate.normalized_value == "синий"


def test_color_bare_word_english() -> None:
    """EN-синоним в заголовке подтверждает русский канон («Black» → «черный»)."""
    card = ProductCard(title="Смартфон Galaxy Black 128GB")
    candidate = _by_code(_extract(card))["color"]
    assert candidate.normalized_value == "черный"


def test_color_template_and_bare_word_deduplicated() -> None:
    """Шаблон и одиночное слово с одним значением дают одного кандидата."""
    card = ProductCard(description="Цвет: чёрный, корпус чёрный")
    colors = [c for c in _extract(card) if c.attribute_code == "color"]
    assert len(colors) == 1


def test_color_out_of_vocab_is_skipped() -> None:
    """Значение вне словаря цветов не угадывается («лавандовый»)."""
    card = ProductCard(description="Цвет: лавандовый")
    assert "color" not in _by_code(_extract(card))


# --- Модель и процессор ------------------------------------------------------


def test_model_after_keyword() -> None:
    """Значение после «Модель:» — латинско-цифровые токены."""
    card = ProductCard(title="Смартфон, модель: SM-S921B")
    candidate = _by_code(_extract(card))["model"]
    assert candidate.normalized_value == "SM-S921B"
    _assert_span_points_to_text(candidate, card.title)


def test_model_stops_at_cyrillic_word() -> None:
    """Кириллица обрывает значение модели («Модель Galaxy Чёрный»)."""
    card = ProductCard(description="Модель Galaxy Чёрный, 128 ГБ")
    candidate = _by_code(_extract(card))["model"]
    assert candidate.normalized_value == "Galaxy"


def test_model_requires_latin_letter() -> None:
    """Чисто числовое значение («Модель 2024») не является моделью."""
    card = ProductCard(description="Модель 2024 года, улучшенная")
    assert "model" not in _by_code(_extract(card))


def test_processor_after_keyword() -> None:
    """Значение после «Процессор» — последовательность латинско-цифровых токенов."""
    card = ProductCard(description="Процессор Qualcomm Snapdragon 8 Gen 2, 8 ядер")
    candidate = _by_code(_extract(card))["processor"]
    assert candidate.normalized_value == "Qualcomm Snapdragon 8 Gen 2"


def test_processor_cpu_keyword() -> None:
    """Английское ключевое слово CPU."""
    card = ProductCard(description="CPU: Apple A18 Pro")
    candidate = _by_code(_extract(card))["processor"]
    assert candidate.normalized_value == "Apple A18 Pro"


# --- Бренд -------------------------------------------------------------------


def _brand_vocab() -> BrandVocab:
    return BrandVocab(
        names=["Acme", "Red"],
        aliases={"acme corp": "Acme"},
        stopwords=["red"],
    )


def test_brand_from_vocab() -> None:
    """Бренд из словаря извлекается с границами слов."""
    card = ProductCard(title="Смартфон Acme X 8/256 ГБ")
    candidate = _by_code(_extract(card, RuleExtractor(_brand_vocab())))["brand"]
    assert candidate.normalized_value == "Acme"
    _assert_span_points_to_text(candidate, card.title)


def test_brand_alias_resolves_to_canonical() -> None:
    """Алиас бренда резолвится в каноническое имя."""
    card = ProductCard(title="Смартфон Acme Corp X")
    candidate = _by_code(_extract(card, RuleExtractor(_brand_vocab())))["brand"]
    assert candidate.normalized_value == "Acme"


def test_brand_without_vocab_not_extracted() -> None:
    """Без словаря брендов правило бренда не работает (нет надёжного признака)."""
    card = ProductCard(title="Смартфон Acme X")
    assert "brand" not in _by_code(_extract(card))


def test_brand_respects_word_boundaries() -> None:
    """Совпадение внутри слова не считается брендом («Acmeon» ≠ «Acme»)."""
    card = ProductCard(title="Смартфон Acmeon 5G")
    assert "brand" not in _by_code(_extract(card, RuleExtractor(_brand_vocab())))


def test_brand_stopword_skipped() -> None:
    """Стоп-слово словаря не превращается в кандидат бренда."""
    card = ProductCard(title="Смартфон Red 5G")
    assert "brand" not in _by_code(_extract(card, RuleExtractor(_brand_vocab())))


# --- Инварианты кандидатов ---------------------------------------------------


def test_candidate_contract_fields() -> None:
    """Кандидат несёт все обязательные поля спеки (Этап 3/9/10/11)."""
    title = "Смартфон Acme X 8/256 ГБ, чёрный"
    card = ProductCard(title=title)
    candidate = _by_code(_extract(card))["storage"]
    assert candidate.extraction_method is ExtractionMethod.RULE
    assert candidate.confidence == DEFAULT_DETERMINISTIC_CONFIDENCE
    assert candidate.is_confirmed_in_text is True
    assert candidate.evidence_text == "8/256 ГБ"
    _assert_span_points_to_text(candidate, title)


def test_grounded_candidates_survive_grounding_filter() -> None:
    """Правила сами подтверждают значения: grounding-фильтр никого не теряет."""
    card = ProductCard(
        title="Смартфон Acme X 8/256 ГБ, чёрный",
        description="Экран 6,7 дюймов, батарея 5000 мА·ч",
    )
    candidates = _extract(card, RuleExtractor(BrandVocab(names=["Acme"])))
    assert len(candidates) >= 5
    kept = GroundingValidator().filter(candidates, card)
    assert len(kept) == len(candidates)


def test_html_in_description_is_stripped_before_matching() -> None:
    """Значения ищутся в очищенном тексте (HTML-теги сняты, Этап 0)."""
    card = ProductCard(description="<b>Батарея 5000 мА·ч</b><br>Съемная")
    candidate = _by_code(_extract(card))["battery_capacity"]
    assert candidate.normalized_value == "5000 мА·ч"
    _assert_span_points_to_text(candidate, card.description)


def test_empty_card_returns_no_candidates() -> None:
    """Пустая карточка → пустой список."""
    assert _extract(ProductCard()) == []


def test_non_rule_card_returns_no_candidates() -> None:
    """Карточка без целевых паттернов не порождает кандидатов."""
    card = ProductCard(title="Ламинат 32 класс 1.5 м²")
    assert _extract(card) == []


def test_extraction_is_deterministic() -> None:
    """Повторный вызов на той же карточке даёт идентичный результат."""
    card = ProductCard(
        title="Смартфон Acme X 8/256 ГБ, чёрный",
        description="Экран 6,7 дюймов, батарея 5000 мА·ч, процессор Unisoc T612",
    )
    extractor = RuleExtractor(BrandVocab(names=["Acme"]))
    first = [c.model_dump() for c in _extract(card, extractor)]
    second = [c.model_dump() for c in _extract(card, extractor)]
    assert first == second

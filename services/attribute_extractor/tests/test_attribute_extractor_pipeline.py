"""Интеграционные тесты оркестратора ExtractPipeline (Этапы 0–11).

Реальные карточки грузятся из gold.jsonl; тумблеры, graceful degradation
(NER без модели), rules-fallback (Этап 7) и формирование статуса проверяются
на устойчивых ожиданиях (структурные, а не на метрики качества правил).
"""

from __future__ import annotations

import json
from pathlib import Path as FsPath

import pytest

from attribute_extractor.config import Settings
from attribute_extractor.constants import (
    AUTO_THRESHOLD,
    CONFLICT_FEATURE_KEY,
    DEFAULT_DETERMINISTIC_CONFIDENCE,
    REVIEW_THRESHOLD,
    RULE_EXTRACTOR_NAME,
)
from attribute_extractor.extractors.base import BaseExtractor
from attribute_extractor.extractors.ner import NER_EXTRACTOR_NAME
from attribute_extractor.normalization import ValueNormalizer
from attribute_extractor.pipeline import ExtractPipeline
from attribute_extractor.preprocessing import CardPreprocessor, SchemaRegistry
from attribute_extractor.references import AttributeVocab, ReferenceCatalog
from specflow_contracts import (
    Attribute,
    AttributeCandidate,
    AttributeValueType,
    ExtractionMethod,
    ExtractionStatus,
    ProductCard,
    Span,
    SpanField,
)

GOLD_PATH = FsPath(__file__).resolve().parents[1] / "gold" / "gold.jsonl"

RECORD_1 = json.loads(GOLD_PATH.read_text(encoding="utf-8").splitlines()[0])


def _card_from_gold(record: dict) -> ProductCard:
    data = record["card"]
    return ProductCard(
        product_id=data["sku_id"],
        title=data["title"],
        description=data["description"],
        category_id=data["category_id"],
        category_name=data["category_name"],
    )


def _default_pipeline(**overrides) -> ExtractPipeline:
    return ExtractPipeline(settings=Settings(**overrides))


def test_gold_card_extract_updates_rule_candidates() -> None:
    card = _card_from_gold(RECORD_1)
    result = _default_pipeline().extract(card)

    by_code = {candidate.attribute_code: candidate for candidate in result.attributes}
    codes = {candidate.attribute_code for candidate in result.attributes}
    assert {"brand", "storage", "ram", "color"} <= codes
    assert by_code["brand"].normalized_value == "realme"
    brand = by_code["brand"]
    assert brand.extraction_method == ExtractionMethod.RULE
    assert brand.is_confirmed_in_text is True
    assert brand.confidence == 0.9
    assert len(brand.source_spans) >= 1
    assert all(
        span.field in (SpanField.TITLE, SpanField.DESCRIPTION) for span in brand.source_spans
    )
    assert result.pipeline_version == "0.1.0"
    assert result.processing_time_ms >= 0
    assert result.low_confidence_count >= 0
    assert result.status in (ExtractionStatus.OK, ExtractionStatus.LOW_CONFIDENCE)
    codes_sorted = [candidate.attribute_code for candidate in result.attributes]
    assert codes_sorted == sorted(codes_sorted)
    assert result.product_id == card.product_id


def test_empty_card_is_skipped() -> None:
    card = ProductCard(title=None, description=None, seller_attributes={"Цвет": "черный"})
    result = _default_pipeline().extract(card)
    assert result.status == ExtractionStatus.SKIPPED
    assert result.attributes == []
    # Подтвердить значения без текста нельзя — карточка на ручной проверке
    # (attribute_extractor.md, §6: пустой список, needs_review=true).
    assert result.needs_review is True


def test_disabled_rules_yields_no_candidates() -> None:
    card = _card_from_gold(RECORD_1)
    result = _default_pipeline(enable_rules=False, enable_ner=False).extract(card)
    assert result.attributes == []
    assert result.status in (ExtractionStatus.OK, ExtractionStatus.PARTIAL)


def test_unavailable_ner_gracefully_degrades_to_rules() -> None:
    card = _card_from_gold(RECORD_1)
    result = _default_pipeline(enable_ner=True).extract(card)
    by_code = {candidate.attribute_code: candidate for candidate in result.attributes}
    assert by_code["brand"].extraction_method == ExtractionMethod.RULE


def _required_schema_registry(category: str = "Смартфоны") -> SchemaRegistry:
    from attribute_extractor.preprocessing import generic_schema

    schema = generic_schema().model_copy(
        update={
            "category": category,
            "required_attributes": [
                Attribute(code="brand", value_type=AttributeValueType.STRING, is_required=True),
                Attribute(
                    code="storage",
                    value_type=AttributeValueType.UNIT_VALUE,
                    is_required=True,
                    unit="ГБ",
                ),
            ],
        }
    )
    return SchemaRegistry([schema])


class _StubNER(BaseExtractor):
    """FAKE NER: доступен, извлекает бренд; совпадает с именем NER-экстрактора."""

    name = NER_EXTRACTOR_NAME
    priority = 10

    def is_available(self) -> bool:
        return True

    def extract(self, card: ProductCard, schema) -> list[AttributeCandidate]:
        span = Span(field=SpanField.TITLE, text="realme", start=9, end=15)
        return [
            AttributeCandidate(
                attribute_code="brand",
                raw_value="realme",
                normalized_value="realme",
                confidence=0.95,
                extraction_method=ExtractionMethod.NER,
                is_confirmed_in_text=True,
                source_spans=[span],
                evidence_text="realme",
                ner_score=0.95,
            )
        ]


def test_ner_candidate_with_rules_fallback_fills_missing_required() -> None:
    registry_required = _required_schema_registry()
    card = _card_from_gold(RECORD_1)
    settings = Settings(normalization_enabled=False)
    pipeline = ExtractPipeline(
        settings=settings,
        registry=_registry_with_stub(),
        preprocessor=CardPreprocessor(schemas=registry_required),
        normalizer=None,
    )
    result = pipeline.extract(card)

    by_code = {candidate.attribute_code: candidate for candidate in result.attributes}
    assert by_code["brand"].extraction_method == ExtractionMethod.NER
    assert by_code["brand"].confidence == 0.95
    assert by_code["brand"].ner_score == 0.95
    assert by_code["storage"].extraction_method == ExtractionMethod.RULE
    assert by_code["storage"].confidence == DEFAULT_DETERMINISTIC_CONFIDENCE
    assert by_code["storage"].ner_score is None
    storage = by_code["storage"].normalized_value
    assert storage.endswith("ГБ")
    codes = {candidate.attribute_code for candidate in result.attributes}
    assert codes == {"brand", "storage"}
    assert result.status == ExtractionStatus.OK


def test_rules_fallback_candidates_keep_deterministic_metadata_end_to_end() -> None:
    """Кандидаты fallback несут rule-метод и ``DEFAULT_DETERMINISTIC_CONFIDENCE``
    после полного каскада (нормализация, слияние, grounding) на настройках
    по умолчанию — Этап 7 фиксирует метаданные, а не наследует их."""
    pipeline = ExtractPipeline(
        settings=Settings(),
        registry=_registry_with_stub(),
        preprocessor=CardPreprocessor(schemas=_required_schema_registry()),
    )
    result = pipeline.extract(_card_from_gold(RECORD_1))

    by_code = {candidate.attribute_code: candidate for candidate in result.attributes}
    storage = by_code["storage"]
    assert storage.extraction_method == ExtractionMethod.RULE
    assert storage.confidence == DEFAULT_DETERMINISTIC_CONFIDENCE
    assert storage.ner_score is None
    assert storage.is_confirmed_in_text is True
    assert by_code["brand"].extraction_method == ExtractionMethod.NER
    assert by_code["brand"].confidence == 0.95


def test_rules_fallback_disabled_keeps_ner_candidates_only() -> None:
    """Тумблер ``enable_rules_fallback`` выключает Этап 7 целиком."""
    pipeline = ExtractPipeline(
        settings=Settings(normalization_enabled=False, enable_rules_fallback=False),
        registry=_registry_with_stub(),
        preprocessor=CardPreprocessor(schemas=_required_schema_registry()),
        normalizer=None,
    )
    result = pipeline.extract(_card_from_gold(RECORD_1))

    codes = {candidate.attribute_code for candidate in result.attributes}
    assert codes == {"brand"}
    assert result.status == ExtractionStatus.PARTIAL
    assert result.needs_review is True


def test_rules_fallback_skips_when_ner_closed_all_required() -> None:
    """Все обязательные закрыты NER-путём — правила не запускаются (Этап 7)."""
    from attribute_extractor.preprocessing import generic_schema

    schema = generic_schema().model_copy(
        update={
            "category": "Смартфоны",
            "required_attributes": [
                Attribute(code="brand", value_type=AttributeValueType.STRING, is_required=True),
            ],
        }
    )
    pipeline = ExtractPipeline(
        settings=Settings(normalization_enabled=False),
        registry=_registry_with_stub(),
        preprocessor=CardPreprocessor(schemas=SchemaRegistry([schema])),
        normalizer=None,
    )
    result = pipeline.extract(_card_from_gold(RECORD_1))

    codes = {candidate.attribute_code for candidate in result.attributes}
    assert codes == {"brand"}
    assert result.status == ExtractionStatus.OK


def _registry_with_stub():
    from attribute_extractor.extractors import ExtractorRegistry
    from attribute_extractor.extractors.rule import RuleExtractor

    return ExtractorRegistry([RuleExtractor(), _StubNER()])


def test_required_missing_marks_partial() -> None:
    card = ProductCard(
        product_id="p2",
        title="Ноутбук без брендов моделей памяти 30 кадров",
        description="Пора перекусить яблоком в 11 часов.",
        category_id="cat",
        category_name="Ноутбуки",
    )
    pipeline = ExtractPipeline(
        settings=Settings(normalization_enabled=False),
        preprocessor=CardPreprocessor(schemas=_required_schema_registry("Ноутбуки")),
    )
    result = pipeline.extract(card)
    assert result.status == ExtractionStatus.PARTIAL
    assert result.needs_review is True


def _enum_schema_registry(category: str = "Смартфоны") -> SchemaRegistry:
    """Схема с единственным обязательным enum-атрибутом (color)."""
    from attribute_extractor.preprocessing import generic_schema

    schema = generic_schema().model_copy(
        update={
            "category": category,
            "required_attributes": [
                Attribute(code="color", value_type=AttributeValueType.ENUM, is_required=True),
            ],
        }
    )
    return SchemaRegistry([schema])


class _StubColorRule(BaseExtractor):
    """FAKE rule-экстрактор: цвет из заголовка, значение отсутствует в vocab."""

    name = RULE_EXTRACTOR_NAME
    priority = 0

    def extract(self, card: ProductCard, schema) -> list[AttributeCandidate]:
        return [
            AttributeCandidate(
                attribute_code="color",
                raw_value="красный",
                normalized_value="красный",
                confidence=DEFAULT_DETERMINISTIC_CONFIDENCE,
                extraction_method=ExtractionMethod.RULE,
                is_confirmed_in_text=True,
                evidence_text="красный",
            )
        ]


def test_enum_out_of_vocab_marks_card_low_confidence() -> None:
    """Enum вне vocab → confidence ниже AUTO → карточка в ``low_confidence``.

    Этап 6 (неуспех маппинга через synonyms_map) вкупе с порогами Этапа 10:
    кандидат остаётся в результате с ``REVIEW_THRESHOLD``, карточка получает
    ``needs_review=true`` и статус ``low_confidence``.
    """
    from attribute_extractor.extractors import ExtractorRegistry

    catalog = ReferenceCatalog()
    catalog.register_attribute_vocab(
        AttributeVocab(attribute_code="color", canonical_values=["Чёрный"])
    )
    pipeline = ExtractPipeline(
        settings=Settings(),
        registry=ExtractorRegistry([_StubColorRule()]),
        preprocessor=CardPreprocessor(schemas=_enum_schema_registry()),
        normalizer=ValueNormalizer(catalog),
    )
    card = ProductCard(
        product_id="p-enum", title="Смартфон цвет красный", category_name="Смартфоны"
    )
    result = pipeline.extract(card)

    assert [candidate.attribute_code for candidate in result.attributes] == ["color"]
    color = result.attributes[0]
    assert color.normalized_value == "красный"
    assert color.confidence == REVIEW_THRESHOLD
    assert result.low_confidence_count == 1
    assert result.needs_review is True
    assert result.status == ExtractionStatus.LOW_CONFIDENCE


def test_enum_in_vocab_keeps_card_ok() -> None:
    """Enum-значение из vocab не снижает уверенность — карточка ``ok``."""
    from attribute_extractor.extractors import ExtractorRegistry

    catalog = ReferenceCatalog()
    catalog.register_attribute_vocab(
        AttributeVocab(attribute_code="color", canonical_values=["Красный"])
    )
    pipeline = ExtractPipeline(
        settings=Settings(),
        registry=ExtractorRegistry([_StubColorRule()]),
        preprocessor=CardPreprocessor(schemas=_enum_schema_registry()),
        normalizer=ValueNormalizer(catalog),
    )
    card = ProductCard(
        product_id="p-enum-ok", title="Смартфон цвет красный", category_name="Смартфоны"
    )
    result = pipeline.extract(card)

    color = result.attributes[0]
    assert color.normalized_value == "Красный"
    assert color.confidence == DEFAULT_DETERMINISTIC_CONFIDENCE
    assert result.low_confidence_count == 0
    assert result.status == ExtractionStatus.OK


class _StubConflictRule(BaseExtractor):
    """FAKE rule-экстрактор: два разных значения одного кода (конфликт)."""

    name = RULE_EXTRACTOR_NAME
    priority = 0

    def extract(self, card: ProductCard, schema) -> list[AttributeCandidate]:
        return [
            AttributeCandidate(
                attribute_code="color",
                raw_value="черный",
                normalized_value="черный",
                confidence=DEFAULT_DETERMINISTIC_CONFIDENCE,
                extraction_method=ExtractionMethod.RULE,
                is_confirmed_in_text=True,
                evidence_text="черный",
            ),
            AttributeCandidate(
                attribute_code="color",
                raw_value="белый",
                normalized_value="белый",
                confidence=REVIEW_THRESHOLD,
                extraction_method=ExtractionMethod.NER,
                is_confirmed_in_text=True,
                evidence_text="белый",
            ),
        ]


def test_conflicting_values_keep_max_confidence_and_mark_low_confidence() -> None:
    """Этап 8: разные значения одного кода → остаётся max confidence с флагом
    конфликта, карточка получает ``needs_review=true`` и статус ``low_confidence``.

    Победитель выше AUTO-порога, поэтому ``low_confidence_count`` не растёт —
    в ``low_confidence`` карточку переводит сам конфликт (Этап 10).
    """
    from attribute_extractor.extractors import ExtractorRegistry

    pipeline = ExtractPipeline(
        settings=Settings(normalization_enabled=False),
        registry=ExtractorRegistry([_StubConflictRule()]),
        normalizer=None,
    )
    card = ProductCard(
        product_id="p-conflict",
        title="Смартфон цвет черный и белый",
        category_name="Смартфоны",
    )
    result = pipeline.extract(card)

    assert [candidate.attribute_code for candidate in result.attributes] == ["color"]
    color = result.attributes[0]
    assert color.normalized_value == "черный"
    assert color.confidence == DEFAULT_DETERMINISTIC_CONFIDENCE
    assert color.features == {CONFLICT_FEATURE_KEY: True}
    assert result.low_confidence_count == 0
    assert result.needs_review is True
    assert result.status == ExtractionStatus.LOW_CONFIDENCE


def test_conflict_with_missing_required_marks_partial() -> None:
    """Конфликт вместе с незакрытым обязательным атрибутом → ``partial``
    имеет приоритет над ``low_confidence``, ``needs_review`` остаётся ``true``."""
    from attribute_extractor.extractors import ExtractorRegistry
    from attribute_extractor.preprocessing import generic_schema

    schema = generic_schema().model_copy(
        update={
            "category": "Смартфоны",
            "required_attributes": [
                Attribute(code="color", value_type=AttributeValueType.ENUM, is_required=True),
                Attribute(
                    code="storage",
                    value_type=AttributeValueType.UNIT_VALUE,
                    is_required=True,
                    unit="ГБ",
                ),
            ],
        }
    )
    pipeline = ExtractPipeline(
        settings=Settings(normalization_enabled=False),
        registry=ExtractorRegistry([_StubConflictRule()]),
        preprocessor=CardPreprocessor(schemas=SchemaRegistry([schema])),
        normalizer=None,
    )
    # Схема требует color и storage; color конфликтует, storage отсутствует.
    card = ProductCard(
        product_id="p-conflict-partial",
        title="Смартфон цвет черный и белый",
        category_name="Смартфоны",
    )
    result = pipeline.extract(card)

    assert [candidate.attribute_code for candidate in result.attributes] == ["color"]
    assert result.attributes[0].features == {CONFLICT_FEATURE_KEY: True}
    assert result.needs_review is True
    assert result.status == ExtractionStatus.PARTIAL


def test_allow_multiple_schema_attribute_still_keeps_single_best_value() -> None:
    """Этап 8 не ветвится по ``allow_multiple``: атрибут схемы с
    ``allow_multiple=true`` получает ровно одно лучшее значение."""
    from attribute_extractor.extractors import ExtractorRegistry
    from attribute_extractor.preprocessing import generic_schema

    schema = generic_schema().model_copy(
        update={
            "category": "Смартфоны",
            "required_attributes": [
                Attribute(
                    code="color",
                    value_type=AttributeValueType.ENUM,
                    is_required=True,
                    allow_multiple=True,
                ),
            ],
        }
    )
    pipeline = ExtractPipeline(
        settings=Settings(normalization_enabled=False),
        registry=ExtractorRegistry([_StubConflictRule()]),
        preprocessor=CardPreprocessor(schemas=SchemaRegistry([schema])),
        normalizer=None,
    )
    card = ProductCard(
        product_id="p-allow-multi",
        title="Смартфон цвет черный и белый",
        category_name="Смартфоны",
    )
    result = pipeline.extract(card)

    assert [candidate.attribute_code for candidate in result.attributes] == ["color"]
    color = result.attributes[0]
    assert color.normalized_value == "черный"
    assert color.confidence == DEFAULT_DETERMINISTIC_CONFIDENCE
    assert color.features == {CONFLICT_FEATURE_KEY: True}
    assert result.needs_review is True
    assert result.status == ExtractionStatus.LOW_CONFIDENCE


class _ScoredStubNER(BaseExtractor):
    """FAKE NER: доступен, отдаёт бренд с заданной модельной оценкой."""

    name = NER_EXTRACTOR_NAME
    priority = 10

    def __init__(self, ner_score: float) -> None:
        self._ner_score = ner_score

    def is_available(self) -> bool:
        return True

    def extract(self, card: ProductCard, schema) -> list[AttributeCandidate]:
        span = Span(field=SpanField.TITLE, text="realme", start=9, end=15)
        return [
            AttributeCandidate(
                attribute_code="brand",
                raw_value="realme",
                normalized_value="realme",
                confidence=1.0,
                extraction_method=ExtractionMethod.NER,
                is_confirmed_in_text=True,
                source_spans=[span],
                evidence_text="realme",
                ner_score=self._ner_score,
            )
        ]


def _brand_only_schema_registry() -> SchemaRegistry:
    from attribute_extractor.preprocessing import generic_schema

    schema = generic_schema().model_copy(
        update={
            "category": "Смартфоны",
            "required_attributes": [
                Attribute(code="brand", value_type=AttributeValueType.STRING, is_required=True),
            ],
        }
    )
    return SchemaRegistry([schema])


@pytest.mark.parametrize(
    ("ner_score", "expected_status"),
    [
        # Границы Этапа 10 (attribute_extractor.md): AUTO_THRESHOLD включительно
        # и выше — ok; чуть ниже AUTO, ровно REVIEW и ниже REVIEW — low_confidence.
        (AUTO_THRESHOLD, ExtractionStatus.OK),
        (0.99, ExtractionStatus.OK),
        (AUTO_THRESHOLD - 0.01, ExtractionStatus.LOW_CONFIDENCE),
        (REVIEW_THRESHOLD, ExtractionStatus.LOW_CONFIDENCE),
        (REVIEW_THRESHOLD - 0.01, ExtractionStatus.LOW_CONFIDENCE),
    ],
)
def test_status_follows_confidence_thresholds(
    ner_score: float, expected_status: ExtractionStatus
) -> None:
    """``needs_review``/``status`` определяются уверенностью по порогам Этапа 10."""
    from attribute_extractor.extractors import ExtractorRegistry

    pipeline = ExtractPipeline(
        settings=Settings(normalization_enabled=False),
        registry=ExtractorRegistry([_ScoredStubNER(ner_score)]),
        preprocessor=CardPreprocessor(schemas=_brand_only_schema_registry()),
        normalizer=None,
    )
    result = pipeline.extract(_card_from_gold(RECORD_1))

    brand = {candidate.attribute_code: candidate for candidate in result.attributes}["brand"]
    assert brand.confidence == pytest.approx(ner_score)
    assert result.status == expected_status
    if expected_status is ExtractionStatus.OK:
        assert result.needs_review is False
        assert result.low_confidence_count == 0
    else:
        assert result.needs_review is True
        assert result.low_confidence_count == 1

"""Тесты расчёта уверенности по методу извлечения (Этап 10).

По openspec/specs/attribute_extractor.md: ``structured``/``rule`` получают
константу ``DETERMINISTIC_CONFIDENCE``, ``ner`` — модельную оценку
``ner_score``; ``match_score`` в уверенность не входит.
"""

from __future__ import annotations

from attribute_extractor.confidence import ConfidenceCalculator
from attribute_extractor.config import Settings
from attribute_extractor.constants import (
    DETERMINISTIC_CONFIDENCE,
    NER_EXTRACTOR_NAME,
    NER_EXTRACTOR_PRIORITY,
    REVIEW_THRESHOLD,
)
from attribute_extractor.extractors.base import BaseExtractor
from attribute_extractor.extractors.registry import ExtractorRegistry
from attribute_extractor.pipeline import ExtractPipeline
from specflow_contracts import (
    AttributeCandidate,
    ExtractionMethod,
    ProductCard,
    Span,
    SpanField,
)


def _candidate(
    method: ExtractionMethod,
    *,
    ner_score: float | None = None,
    confidence: float = 0.5,
) -> AttributeCandidate:
    return AttributeCandidate(
        attribute_code="brand",
        raw_value="realme",
        normalized_value="realme",
        confidence=confidence,
        extraction_method=method,
        is_confirmed_in_text=True,
        ner_score=ner_score,
    )


def test_rule_and_structured_use_deterministic_constant() -> None:
    calculator = ConfidenceCalculator()

    for method in (ExtractionMethod.RULE, ExtractionMethod.STRUCTURED):
        assert calculator.candidate_conf(_candidate(method)) == DETERMINISTIC_CONFIDENCE


def test_ner_uses_ner_score() -> None:
    calculator = ConfidenceCalculator()

    assert calculator.candidate_conf(_candidate(ExtractionMethod.NER, ner_score=0.73)) == 0.73


def test_ner_without_score_falls_back_to_review_threshold() -> None:
    """NER-кандидат без оценки модели не может быть уверенным."""
    calculator = ConfidenceCalculator()

    candidate = _candidate(ExtractionMethod.NER, ner_score=None)
    assert calculator.candidate_conf(candidate) == REVIEW_THRESHOLD


def test_deterministic_confidence_is_configurable() -> None:
    calculator = ConfidenceCalculator(deterministic_confidence=0.7)

    assert calculator.candidate_conf(_candidate(ExtractionMethod.RULE)) == 0.7


def test_apply_overwrites_confidence_by_method_without_mutation() -> None:
    calculator = ConfidenceCalculator()
    candidates = [
        _candidate(ExtractionMethod.RULE, confidence=0.1),
        _candidate(ExtractionMethod.NER, ner_score=0.95, confidence=0.1),
    ]

    scored = calculator.apply(candidates)

    assert [candidate.confidence for candidate in scored] == [DETERMINISTIC_CONFIDENCE, 0.95]
    assert [candidate.confidence for candidate in candidates] == [0.1, 0.1]


class _StubNER(BaseExtractor):
    """FAKE NER: отдаёт кандидата с заведомо неверной ``confidence`` и ``ner_score``."""

    name = NER_EXTRACTOR_NAME
    priority = NER_EXTRACTOR_PRIORITY

    def is_available(self) -> bool:
        return True

    def extract(self, card: ProductCard, schema) -> list[AttributeCandidate]:
        return [
            AttributeCandidate(
                attribute_code="brand",
                raw_value="realme",
                normalized_value="realme",
                confidence=0.10,
                extraction_method=ExtractionMethod.NER,
                is_confirmed_in_text=True,
                source_spans=[Span(field=SpanField.TITLE, text="realme", start=9, end=15)],
                evidence_text="realme",
                ner_score=0.90,
            )
        ]


def test_pipeline_sets_ner_confidence_from_ner_score() -> None:
    """Оркестратор пересчитывает уверенность NER-кандидата из ``ner_score``."""
    pipeline = ExtractPipeline(
        settings=Settings(normalization_enabled=False, grounding_required=False),
        registry=ExtractorRegistry([_StubNER()]),
    )
    card = ProductCard(product_id="p-conf", title="Смартфон realme", category_name="Смартфоны")

    result = pipeline.extract(card)

    assert [candidate.attribute_code for candidate in result.attributes] == ["brand"]
    brand = result.attributes[0]
    assert brand.extraction_method == ExtractionMethod.NER
    assert brand.confidence == 0.90
    assert brand.ner_score == 0.90

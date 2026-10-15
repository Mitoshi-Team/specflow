"""Тесты объединения кандидатов атрибутов (Этап 4)."""

from __future__ import annotations

import pytest

from attribute_extractor.constants import CONFLICT_FEATURE_KEY
from attribute_extractor.merging import CandidateMerger
from specflow_contracts import AttributeCandidate, ExtractionMethod, Span, SpanField


def _candidate(
    value: str = "black",
    *,
    code: str = "color",
    method: ExtractionMethod = ExtractionMethod.RULE,
    confidence: float = 0.9,
    confirmed: bool = True,
    spans: list[Span] | None = None,
    evidence: str | None = None,
    features: dict[str, object] | None = None,
) -> AttributeCandidate:
    return AttributeCandidate(
        attribute_code=code,
        raw_value=value,
        normalized_value=value,
        confidence=confidence,
        extraction_method=method,
        is_confirmed_in_text=confirmed,
        source_spans=spans or [],
        evidence_text=evidence,
        features=features,
    )


def test_merge_empty_returns_empty() -> None:
    """Пустой список кандидатов остаётся пустым."""
    assert CandidateMerger().merge([]) == []


def test_merge_groups_same_code_and_value() -> None:
    """Кандидаты с одинаковой парой (code, value) объединяются в одного."""
    merger = CandidateMerger()
    result = merger.merge(
        [
            _candidate(confidence=0.9, method=ExtractionMethod.RULE),
            _candidate(confidence=0.7, method=ExtractionMethod.DICT),
        ]
    )
    assert len(result) == 1
    assert result[0].attribute_code == "color"
    assert result[0].normalized_value == "black"
    assert result[0].is_confirmed_in_text is True


def test_merge_weighted_confidence_formula() -> None:
    """Уверенность агрегируется по формуле с весами методов."""
    merger = CandidateMerger()
    result = merger.merge(
        [
            _candidate(confidence=0.9, method=ExtractionMethod.RULE),
            _candidate(confidence=0.7, method=ExtractionMethod.DICT),
        ]
    )
    expected = (1.00 * 0.9 + 0.98 * 0.7) / (1.00 + 0.98)
    assert result[0].confidence == pytest.approx(expected)


def test_merge_excludes_unconfirmed_from_aggregation() -> None:
    """Неподтверждённый кандидат не участвует в агрегации (g_m = 0)."""
    merger = CandidateMerger()
    result = merger.merge(
        [
            _candidate(confidence=0.9, method=ExtractionMethod.RULE, confirmed=True),
            _candidate(confidence=0.5, method=ExtractionMethod.LLM, confirmed=False),
        ]
    )
    assert result[0].confidence == pytest.approx(0.9)
    assert result[0].is_confirmed_in_text is True


def test_merge_all_unconfirmed_uses_weighted_average() -> None:
    """Если никто не подтверждён, агрегация идёт без grounding-множителя."""
    merger = CandidateMerger()
    result = merger.merge(
        [
            _candidate(confidence=0.8, method=ExtractionMethod.RULE, confirmed=False),
            _candidate(confidence=0.6, method=ExtractionMethod.DICT, confirmed=False),
        ]
    )
    expected = (1.00 * 0.8 + 0.98 * 0.6) / (1.00 + 0.98)
    assert result[0].confidence == pytest.approx(expected)
    assert result[0].is_confirmed_in_text is False


def test_merge_different_methods_produce_hybrid() -> None:
    """Объединение разных методов даёт extraction_method=hybrid."""
    merger = CandidateMerger()
    result = merger.merge(
        [
            _candidate(method=ExtractionMethod.RULE),
            _candidate(method=ExtractionMethod.DICT),
        ]
    )
    assert result[0].extraction_method is ExtractionMethod.HYBRID


def test_merge_same_method_is_preserved() -> None:
    """Если все кандидаты одним методом, он сохраняется."""
    merger = CandidateMerger()
    result = merger.merge(
        [
            _candidate(method=ExtractionMethod.NER, confidence=0.6),
            _candidate(method=ExtractionMethod.NER, confidence=0.8),
        ]
    )
    assert result[0].extraction_method is ExtractionMethod.NER


def test_merge_unions_source_spans_without_duplicates() -> None:
    """source_spans объединяются, дубликаты устраняются."""
    merger = CandidateMerger()
    shared = Span(field=SpanField.TITLE, text="black", start=0, end=5)
    extra = Span(field=SpanField.DESCRIPTION, text="black", start=10, end=15)
    result = merger.merge(
        [
            _candidate(spans=[shared]),
            _candidate(spans=[shared, extra]),
        ]
    )
    assert result[0].source_spans == [shared, extra]


def test_conflict_both_grounded_keeps_both_with_penalty_and_flag() -> None:
    """Разные подтверждённые значения одного атрибута — оба с штрафом и флагом."""
    merger = CandidateMerger()
    result = merger.merge(
        [
            _candidate("black", confidence=0.9, method=ExtractionMethod.RULE),
            _candidate("white", confidence=0.8, method=ExtractionMethod.DICT),
        ]
    )
    assert len(result) == 2
    by_value = {candidate.normalized_value: candidate for candidate in result}
    assert by_value["black"].confidence == pytest.approx(0.8)
    assert by_value["white"].confidence == pytest.approx(0.7)
    assert by_value["black"].features == {CONFLICT_FEATURE_KEY: True}
    assert by_value["white"].features == {CONFLICT_FEATURE_KEY: True}


def test_conflict_one_grounded_drops_unconfirmed() -> None:
    """При подтверждённом и неподтверждённом значении остаётся подтверждённое."""
    merger = CandidateMerger()
    result = merger.merge(
        [
            _candidate("black", confidence=0.9, method=ExtractionMethod.RULE, confirmed=True),
            _candidate("white", confidence=0.95, method=ExtractionMethod.DICT, confirmed=False),
        ]
    )
    assert len(result) == 1
    assert result[0].normalized_value == "black"
    assert result[0].features is None


def test_conflict_none_grounded_keeps_highest_weight() -> None:
    """Без подтверждений остаётся значение с наибольшим весом метода."""
    merger = CandidateMerger()
    result = merger.merge(
        [
            _candidate("black", confidence=0.5, method=ExtractionMethod.RULE, confirmed=False),
            _candidate("white", confidence=0.9, method=ExtractionMethod.LLM, confirmed=False),
        ]
    )
    assert len(result) == 1
    assert result[0].normalized_value == "black"


def test_different_codes_are_not_merged() -> None:
    """Значения разных атрибутов не конфликтуют и сохраняются оба."""
    merger = CandidateMerger()
    result = merger.merge(
        [
            _candidate("black", code="color"),
            _candidate("6.7", code="screen_size"),
        ]
    )
    assert {candidate.attribute_code for candidate in result} == {"color", "screen_size"}


def test_same_value_different_codes_stay_separate() -> None:
    """Одинаковое значение разных атрибутов не объединяется."""
    merger = CandidateMerger()
    result = merger.merge(
        [
            _candidate("128", code="ram"),
            _candidate("128", code="storage"),
        ]
    )
    assert len(result) == 2


def test_configurable_method_weights() -> None:
    """Веса методов конфигурируемы и влияют на агрегацию."""
    merger = CandidateMerger({"rule": 0.5, "dict": 1.0})
    result = merger.merge(
        [
            _candidate("black", confidence=1.0, method=ExtractionMethod.RULE),
            _candidate("black", confidence=0.0, method=ExtractionMethod.DICT),
        ]
    )
    expected = (0.5 * 1.0 + 1.0 * 0.0) / (0.5 + 1.0)
    assert result[0].confidence == pytest.approx(expected)

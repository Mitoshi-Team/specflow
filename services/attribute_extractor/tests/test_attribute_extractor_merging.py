"""Тесты объединения кандидатов атрибутов."""

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
    result = CandidateMerger().merge(
        [
            _candidate(confidence=0.9, method=ExtractionMethod.RULE),
            _candidate(confidence=0.7, method=ExtractionMethod.NER),
        ]
    )
    assert len(result) == 1
    assert result[0].attribute_code == "color"
    assert result[0].normalized_value == "black"
    assert result[0].is_confirmed_in_text is True


def test_merge_takes_max_confidence() -> None:
    """Внутри группы берётся максимальная уверенность (без взвешивания)."""
    result = CandidateMerger().merge(
        [
            _candidate(confidence=0.9, method=ExtractionMethod.RULE),
            _candidate(confidence=0.7, method=ExtractionMethod.NER),
        ]
    )
    assert result[0].confidence == pytest.approx(0.9)
    assert result[0].extraction_method is ExtractionMethod.RULE


def test_merge_confirmed_flag_is_any() -> None:
    """Подтверждение группы: достаточно, чтобы хотя бы один кандидат был подтверждён."""
    result = CandidateMerger().merge(
        [
            _candidate(confidence=0.9, method=ExtractionMethod.RULE, confirmed=True),
            _candidate(confidence=0.5, method=ExtractionMethod.NER, confirmed=False),
        ]
    )
    assert result[0].confidence == pytest.approx(0.9)
    assert result[0].is_confirmed_in_text is True


def test_merge_all_unconfirmed_takes_max() -> None:
    """Без подтверждений тоже берётся максимальная уверенность."""
    result = CandidateMerger().merge(
        [
            _candidate(confidence=0.8, method=ExtractionMethod.RULE, confirmed=False),
            _candidate(confidence=0.6, method=ExtractionMethod.NER, confirmed=False),
        ]
    )
    assert result[0].confidence == pytest.approx(0.8)
    assert result[0].is_confirmed_in_text is False


def test_merge_keeps_method_of_best_candidate() -> None:
    """Метод результата — метод кандидата с максимальной уверенностью (гибрида нет)."""
    result = CandidateMerger().merge(
        [
            _candidate(method=ExtractionMethod.RULE, confidence=0.7),
            _candidate(method=ExtractionMethod.NER, confidence=0.9),
        ]
    )
    assert result[0].extraction_method is ExtractionMethod.NER


def test_merge_same_method_is_preserved() -> None:
    """Если все кандидаты одним методом, он сохраняется."""
    result = CandidateMerger().merge(
        [
            _candidate(method=ExtractionMethod.NER, confidence=0.6),
            _candidate(method=ExtractionMethod.NER, confidence=0.8),
        ]
    )
    assert result[0].extraction_method is ExtractionMethod.NER


def test_merge_unions_source_spans_without_duplicates() -> None:
    """source_spans объединяются, дубликаты устраняются."""
    shared = Span(field=SpanField.TITLE, text="black", start=0, end=5)
    extra = Span(field=SpanField.DESCRIPTION, text="black", start=10, end=15)
    result = CandidateMerger().merge(
        [
            _candidate(spans=[shared]),
            _candidate(spans=[shared, extra]),
        ]
    )
    assert result[0].source_spans == [shared, extra]


def test_conflict_keeps_max_confidence_with_flag() -> None:
    """Разные значения одного атрибута: остаётся max confidence с флагом конфликта."""
    result = CandidateMerger().merge(
        [
            _candidate("black", confidence=0.9, method=ExtractionMethod.RULE),
            _candidate("white", confidence=0.8, method=ExtractionMethod.NER),
        ]
    )
    assert len(result) == 1
    assert result[0].normalized_value == "black"
    assert result[0].features == {CONFLICT_FEATURE_KEY: True}


def test_conflict_without_penalty() -> None:
    """Конфликт не снижает уверенность (штрафов больше нет)."""
    result = CandidateMerger().merge(
        [
            _candidate("black", confidence=0.9),
            _candidate("white", confidence=0.5),
        ]
    )
    assert result[0].confidence == pytest.approx(0.9)
    assert result[0].features == {CONFLICT_FEATURE_KEY: True}


def test_conflict_ignores_grounding_preference() -> None:
    """Grounding-статус не влияет на выбор: побеждает max confidence
    (hard-filter неподтверждённых выполняет отдельный этап grounding)."""
    result = CandidateMerger().merge(
        [
            _candidate("black", confidence=0.9, method=ExtractionMethod.RULE, confirmed=True),
            _candidate("white", confidence=0.95, method=ExtractionMethod.NER, confirmed=False),
        ]
    )
    assert len(result) == 1
    assert result[0].normalized_value == "white"
    assert result[0].is_confirmed_in_text is False
    assert result[0].features == {CONFLICT_FEATURE_KEY: True}


def test_different_codes_are_not_merged() -> None:
    """Значения разных атрибутов не конфликтуют и сохраняются оба."""
    result = CandidateMerger().merge(
        [
            _candidate("black", code="color"),
            _candidate("6.7", code="screen_size"),
        ]
    )
    assert {candidate.attribute_code for candidate in result} == {"color", "screen_size"}


def test_same_value_different_codes_stay_separate() -> None:
    """Одинаковое значение разных атрибутов не объединяется."""
    result = CandidateMerger().merge(
        [
            _candidate("128", code="ram"),
            _candidate("128", code="storage"),
        ]
    )
    assert len(result) == 2


def test_conflict_merges_features_from_kept_candidate() -> None:
    """Флаг конфликта сохраняет остальные features кандидата-победителя."""
    result = CandidateMerger().merge(
        [
            _candidate("black", confidence=0.9, features={"source": "rule"}),
            _candidate("white", confidence=0.5),
        ]
    )
    assert result[0].features == {"source": "rule", CONFLICT_FEATURE_KEY: True}

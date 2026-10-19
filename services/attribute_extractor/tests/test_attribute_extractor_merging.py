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
    ner_score: float | None = None,
    match_score: float | None = None,
    is_new_field: bool = False,
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
        ner_score=ner_score,
        match_score=match_score,
        is_new_field=is_new_field,
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


def test_merge_same_value_keeps_payload_of_best_candidate() -> None:
    """При одинаковом ``normalized_value`` остаётся лучший по confidence:
    его raw_value/evidence сохраняются, спаны дублей объединяются без потерь."""
    winner = AttributeCandidate(
        attribute_code="color",
        raw_value="чёрный",
        normalized_value="чёрный",
        confidence=0.9,
        extraction_method=ExtractionMethod.RULE,
        is_confirmed_in_text=True,
        source_spans=[Span(field=SpanField.TITLE, text="чёрный", start=0, end=6)],
        evidence_text="Цвет корпуса: чёрный",
    )
    duplicate = AttributeCandidate(
        attribute_code="color",
        raw_value="Black",
        normalized_value="чёрный",
        confidence=0.7,
        extraction_method=ExtractionMethod.NER,
        is_confirmed_in_text=True,
        source_spans=[Span(field=SpanField.DESCRIPTION, text="Black", start=20, end=25)],
        evidence_text="Black",
        ner_score=0.7,
    )
    result = CandidateMerger().merge([duplicate, winner])
    assert len(result) == 1
    assert result[0].raw_value == "чёрный"
    assert result[0].evidence_text == "Цвет корпуса: чёрный"
    assert result[0].confidence == pytest.approx(0.9)
    # Спаны объединяются в порядке первого появления кандидатов на входе.
    assert result[0].source_spans == duplicate.source_spans + winner.source_spans


def test_merge_collapses_identical_duplicate_candidates() -> None:
    """Полностью идентичные дубликаты (одинаковые код/значение/спаны) схлопываются."""
    result = CandidateMerger().merge(
        [
            _candidate(spans=[Span(field=SpanField.TITLE, text="black", start=0, end=5)]),
            _candidate(spans=[Span(field=SpanField.TITLE, text="black", start=0, end=5)]),
        ]
    )
    assert len(result) == 1
    assert result[0].source_spans == [Span(field=SpanField.TITLE, text="black", start=0, end=5)]


def test_merge_dedups_repeated_spans_within_one_candidate() -> None:
    """Повтор спана внутри одного кандидата тоже устраняется при объединении."""
    span = Span(field=SpanField.DESCRIPTION, text="black", start=10, end=15)
    result = CandidateMerger().merge([_candidate(spans=[span, span]), _candidate(spans=[span])])
    assert result[0].source_spans == [span]


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


def test_merge_preserves_tracing_fields_of_best_candidate() -> None:
    """ner_score/match_score/is_new_field победителя сохраняются при объединении."""
    result = CandidateMerger().merge(
        [
            _candidate(
                method=ExtractionMethod.NER,
                confidence=0.95,
                ner_score=0.95,
                match_score=0.81,
                is_new_field=True,
            ),
            _candidate(method=ExtractionMethod.NER, confidence=0.6, ner_score=0.6),
        ]
    )
    assert len(result) == 1
    assert result[0].ner_score == pytest.approx(0.95)
    assert result[0].match_score == pytest.approx(0.81)
    assert result[0].is_new_field is True


def test_conflict_preserves_tracing_fields_of_best_candidate() -> None:
    """При конфликте трассировочные поля берутся у победителя по confidence."""
    result = CandidateMerger().merge(
        [
            _candidate("black", confidence=0.9, ner_score=0.9, match_score=0.7, is_new_field=True),
            _candidate("white", confidence=0.5, ner_score=0.5),
        ]
    )
    assert result[0].normalized_value == "black"
    assert result[0].ner_score == pytest.approx(0.9)
    assert result[0].match_score == pytest.approx(0.7)
    assert result[0].is_new_field is True


def test_conflict_excludes_spans_of_losing_value() -> None:
    """Спаны кандидатов с проигравшим значением не попадают в результат."""
    winner_span = Span(field=SpanField.TITLE, text="black", start=0, end=5)
    loser_span = Span(field=SpanField.DESCRIPTION, text="white", start=10, end=15)
    result = CandidateMerger().merge(
        [
            _candidate("black", confidence=0.9, spans=[winner_span]),
            _candidate("white", confidence=0.5, spans=[loser_span]),
        ]
    )
    assert result[0].source_spans == [winner_span]


def test_conflict_excludes_features_of_losing_value() -> None:
    """Features кандидатов с проигравшим значением не попадают в результат."""
    result = CandidateMerger().merge(
        [
            _candidate("black", confidence=0.9),
            _candidate("white", confidence=0.5, features={"source": "ner"}),
        ]
    )
    assert result[0].features == {CONFLICT_FEATURE_KEY: True}


def test_conflict_merges_spans_of_winning_value_duplicates() -> None:
    """Дубли одного значения внутри конфликтной группы сливаются по-прежнему."""
    span_a = Span(field=SpanField.TITLE, text="black", start=0, end=5)
    span_b = Span(field=SpanField.DESCRIPTION, text="black", start=20, end=25)
    loser_span = Span(field=SpanField.TITLE, text="white", start=30, end=35)
    result = CandidateMerger().merge(
        [
            _candidate("black", confidence=0.9, spans=[span_a]),
            _candidate("black", confidence=0.7, spans=[span_b]),
            _candidate("white", confidence=0.5, spans=[loser_span]),
        ]
    )
    assert result[0].source_spans == [span_a, span_b]
    assert result[0].features == {CONFLICT_FEATURE_KEY: True}


def test_conflict_confirmed_flag_counts_only_winning_value() -> None:
    """Подтверждение учитывается только среди кандидатов с победившим значением."""
    result = CandidateMerger().merge(
        [
            _candidate("black", confidence=0.9, confirmed=False),
            _candidate("white", confidence=0.5, confirmed=True),
        ]
    )
    assert result[0].is_confirmed_in_text is False
    assert result[0].features == {CONFLICT_FEATURE_KEY: True}


def test_merge_keeps_single_best_value_unconditionally() -> None:
    """Множество разных значений одного кода схлопывается в лучшее.

    Мёржа безусловна: поле ``allow_multiple`` схемы в кандидаты не попадает
    и не влияет на выбор (см. модуль ``merging``), поэтому здесь остаётся
    ровно один кандидат с максимальной уверенностью и флагом конфликта.
    """
    result = CandidateMerger().merge(
        [
            _candidate("black", confidence=0.6),
            _candidate("white", confidence=0.9),
            _candidate("green", confidence=0.7),
        ]
    )
    assert len(result) == 1
    assert result[0].normalized_value == "white"
    assert result[0].confidence == pytest.approx(0.9)
    assert result[0].features == {CONFLICT_FEATURE_KEY: True}

"""Тесты декодера BIO → NERSpan (задача 3).

Модель/токенизатор не загружаются: проверяется чистая функция ``decode_bio``.
"""

from __future__ import annotations

from attribute_extractor.ner_model import decode_bio, filter_spans


def _span(text: str, score: float):
    from attribute_extractor.extractors.ner import NERSpan

    return NERSpan(text=text, label="PROPERTY", start=0, end=len(text), score=score)


def test_filter_spans_keeps_high_confidence():
    spans = [_span("a", 0.9), _span("b", 0.5)]
    kept = filter_spans(spans, min_score=0.85)
    assert [s.text for s in kept] == ["a"]


def test_filter_spans_keeps_exact_threshold():
    spans = [_span("a", 0.85)]
    assert [s.text for s in filter_spans(spans, min_score=0.85)] == ["a"]


def test_decode_bio_merges_consecutive_tokens():
    text = 'Диагональ экрана 6.7"'
    tokens = [
        (0, 9, "B-CHARACTERISTIC", 0.9),
        (10, 16, "I-CHARACTERISTIC", 0.8),
        (17, 20, "B-PROPERTY", 0.95),
    ]
    spans = decode_bio(text, tokens)
    assert [(s.text, s.label) for s in spans] == [
        ("Диагональ экрана", "CHARACTERISTIC"),
        ("6.7", "PROPERTY"),
    ]
    assert spans[0].start == 0 and spans[0].end == 16
    assert spans[1].score == 0.95


def test_decode_bio_span_score_is_minimum():
    spans = decode_bio(
        "abc",
        [(0, 1, "B-PROPERTY", 0.9), (1, 3, "I-PROPERTY", 0.6)],
    )
    assert spans[0].score == 0.6


def test_decode_bio_inside_without_begin_starts_new_span():
    spans = decode_bio(
        "abc",
        [(0, 2, "I-PROPERTY", 0.7), (2, 3, "I-PROPERTY", 0.7)],
    )
    assert len(spans) == 1
    assert (spans[0].start, spans[0].end) == (0, 3)


def test_decode_bio_class_change_splits_span():
    spans = decode_bio(
        "abcdef",
        [
            (0, 3, "B-PROPERTY", 0.9),
            (3, 6, "B-CHARACTERISTIC", 0.9),
        ],
    )
    assert [s.label for s in spans] == ["PROPERTY", "CHARACTERISTIC"]


def test_decode_bio_outside_flushes_and_skips_empty_tokens():
    spans = decode_bio(
        "abc",
        [(0, 1, "B-PROPERTY", 0.9), (1, 1, "I-PROPERTY", 0.9), (1, 2, "O", 0.9)],
    )
    assert len(spans) == 1
    assert (spans[0].start, spans[0].end) == (0, 1)


def test_decode_bio_zero_gap_merges_adjacent_subwords():
    """Подслова одного слова склеиваются независимо от B-/I- префикса."""
    text = "Восстановленный"
    spans = decode_bio(
        text,
        [
            (0, 9, "B-PROPERTY", 1.0),
            (9, 15, "B-PROPERTY", 0.8),
        ],
    )
    assert [(s.text, s.label) for s in spans] == [(text, "PROPERTY")]
    assert spans[0].score == 0.8


def test_decode_bio_gap_splits_same_class_values():
    """Два значения одного класса, разделённые пробелом — разные спаны."""
    text = "Apple iPhone"
    spans = decode_bio(
        text,
        [
            (0, 5, "B-PROPERTY", 1.0),
            (6, 12, "B-PROPERTY", 1.0),
        ],
    )
    assert [s.text for s in spans] == ["Apple", "iPhone"]


def test_decode_bio_inside_continues_multiword_value():
    """I- продолжение через пробел остаётся одним значением."""
    text = "iPhone 11"
    spans = decode_bio(
        text,
        [
            (0, 6, "B-PROPERTY", 0.99),
            (7, 9, "I-PROPERTY", 0.95),
        ],
    )
    assert [(s.text, s.score) for s in spans] == [("iPhone 11", 0.95)]


def test_decode_bio_expand_words_extends_truncated_value():
    """Обрыв значения на подслове расширяется до границы слова."""
    text = "цвет серебристый"
    spans = decode_bio(
        text,
        [
            (0, 4, "B-CHARACTERISTIC", 1.0),
            (5, 14, "B-PROPERTY", 0.9),
        ],
        expand_words=True,
    )
    assert [(s.text, s.label) for s in spans] == [
        ("цвет", "CHARACTERISTIC"),
        ("серебристый", "PROPERTY"),
    ]

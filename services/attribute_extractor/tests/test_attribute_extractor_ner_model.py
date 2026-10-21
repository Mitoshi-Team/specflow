"""Тесты декодера BIO → NERSpan (задача 3).

Модель/токенизатор не загружаются: проверяется чистая функция ``decode_bio``.
"""

from __future__ import annotations

from attribute_extractor.ner_model import decode_bio


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

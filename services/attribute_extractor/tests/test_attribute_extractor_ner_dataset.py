"""Тесты подготовки BIO-датасета для NER (задача 3)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from attribute_extractor.ner_dataset import (
    LABEL2ID,
    LABELS,
    align_labels,
    load_weak_records,
    records_to_examples,
    tokenize_words,
)

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "train_ner.py"
_spec = importlib.util.spec_from_file_location("train_ner", _SCRIPT)
assert _spec is not None and _spec.loader is not None
train_ner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(train_ner)


def test_tokenize_words_offsets_are_absolute():
    text = "  Смартфон  Apple iPhone  "
    words = tokenize_words(text)
    assert [word.text for word in words] == ["Смартфон", "Apple", "iPhone"]
    assert all(text[word.start : word.end] == word.text for word in words)


def test_align_labels_marks_begin_and_inside():
    text = "Диагональ экрана: 6.7 дюйма"
    words = tokenize_words(text)
    start_char = text.index("Диагональ")
    end_char = text.index(":") - 1
    spans = [
        {"start": start_char, "end": end_char, "label": "CHARACTERISTIC"},
        {"start": text.index("6.7"), "end": text.index("6.7") + 3, "label": "PROPERTY"},
    ]
    labels = align_labels(words, spans)
    assert labels == [
        "B-CHARACTERISTIC",
        "I-CHARACTERISTIC",
        "B-PROPERTY",
        "O",
    ]


def test_align_labels_property_wins_on_overlap():
    words = tokenize_words("Аккумулятор 5000 мАч")
    spans = [
        {"start": 0, "end": 11, "label": "CHARACTERISTIC"},
        {"start": 12, "end": 16, "label": "PROPERTY"},
        {"start": 0, "end": 16, "label": "PROPERTY"},
    ]
    labels = align_labels(words, spans)
    assert labels[0] == "B-PROPERTY"
    assert labels[1] == "I-PROPERTY"


def test_align_labels_ignores_unknown_labels_and_bad_offsets():
    words = tokenize_words("Цвет: чёрный")
    labels = align_labels(
        words,
        [
            {"start": None, "end": 4, "label": "CHARACTERISTIC"},
            {"start": 0, "end": 4, "label": "OTHER"},
        ],
    )
    assert labels == ["O", "O"]


def test_load_and_convert_weak_records(tmp_path):
    source = tmp_path / "weak.jsonl"
    record = {
        "text": "Цвет: чёрный",
        "spans": [
            {"start": 0, "end": 4, "label": "CHARACTERISTIC", "attribute_code": None},
            {"start": 6, "end": 12, "label": "PROPERTY", "attribute_code": "color"},
        ],
        "sku_id": 1,
        "category_name": "Смартфоны",
    }
    source.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    examples = records_to_examples(load_weak_records(source))
    assert len(examples) == 1
    assert examples[0].words == ["Цвет:", "чёрный"]
    assert examples[0].labels == ["B-CHARACTERISTIC", "B-PROPERTY"]


def test_labels_are_consistent_with_label2id():
    assert LABELS[0] == "O"
    assert len(LABEL2ID) == len(LABELS)
    assert all(LABEL2ID[label] == index for index, label in enumerate(LABELS))


def test_entity_spans_groups_bio_sequences():
    labels = ["O", "B-PROPERTY", "I-PROPERTY", "O", "B-CHARACTERISTIC"]
    assert train_ner.entity_spans(labels) == {
        ("PROPERTY", 1, 3),
        ("CHARACTERISTIC", 4, 5),
    }


def test_entity_spans_recovers_inside_without_begin():
    assert train_ner.entity_spans(["I-PROPERTY", "I-PROPERTY"]) == {("PROPERTY", 0, 2)}


def test_micro_scores_counts_tp_fp_fn():
    true = [{("PROPERTY", 0, 1)}, {("CHARACTERISTIC", 0, 1)}]
    pred = [{("PROPERTY", 0, 1)}, {("PROPERTY", 0, 1)}]
    scores = train_ner.micro_scores(true, pred)
    assert scores["tp"] == 1.0
    assert scores["fp"] == 1.0
    assert scores["fn"] == 1.0
    assert scores["precision"] == 0.5
    assert scores["recall"] == 0.5
    assert scores["f1"] == 0.5

"""Подготовка BIO-датасета для обучения NER по weak-разметке.

Weak-датасет (``make_ner_weak_dataset.py``) содержит записи
``{"text", "spans": [{start, end, label, attribute_code}], ...}``, где
``label`` — ``CHARACTERISTIC`` или ``PROPERTY``. Для token-classification
текст режется на слова (пробельные границы), каждому слову присваивается
BIO-метка. Слово считается частью сущности, если пересекается со спаном;
первое слово сущности получает ``B-``, последующие — ``I-``. При пересечении
спанов разных классов приоритет у ``PROPERTY`` (значение важнее имени поля).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from attribute_extractor.constants import (
    NER_BIO_OUTSIDE,
    NER_BIO_PREFIX_BEGIN,
    NER_BIO_PREFIX_INSIDE,
    NER_LABEL_CHARACTERISTIC,
    NER_LABEL_PROPERTY,
)

_WORD_PATTERN = re.compile(r"\S+")

LABELS = [
    NER_BIO_OUTSIDE,
    f"{NER_BIO_PREFIX_BEGIN}{NER_LABEL_CHARACTERISTIC}",
    f"{NER_BIO_PREFIX_INSIDE}{NER_LABEL_CHARACTERISTIC}",
    f"{NER_BIO_PREFIX_BEGIN}{NER_LABEL_PROPERTY}",
    f"{NER_BIO_PREFIX_INSIDE}{NER_LABEL_PROPERTY}",
]
"""BIO-метки в фиксированном порядке (id = индекс)."""

LABEL2ID = {label: idx for idx, label in enumerate(LABELS)}


@dataclass(frozen=True)
class WordSpan:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class BioExample:
    words: list[str]
    labels: list[str]


def tokenize_words(text: str) -> list[WordSpan]:
    """Разбить текст на слова с абсолютными смещениями."""
    return [
        WordSpan(text=m.group(), start=m.start(), end=m.end()) for m in _WORD_PATTERN.finditer(text)
    ]


def _overlap(word: WordSpan, start: int, end: int) -> bool:
    return word.start < end and start < word.end


def align_labels(
    words: Sequence[WordSpan],
    spans: Iterable[dict],
) -> list[str]:
    """Сопоставить спаны словам и вернуть BIO-метки по словам."""
    labels = [NER_BIO_OUTSIDE] * len(words)
    # PROPERTY приоритетнее CHARACTERISTIC при пересечении:
    # сначала пишем менее приоритетные, затем перекрываем PROPERTY.
    ordered = sorted(
        spans,
        key=lambda span: 0 if span.get("label") == NER_LABEL_CHARACTERISTIC else 1,
    )
    for span in ordered:
        start = span.get("start")
        end = span.get("end")
        label = span.get("label")
        if (
            start is None
            or end is None
            or label
            not in (
                NER_LABEL_CHARACTERISTIC,
                NER_LABEL_PROPERTY,
            )
        ):
            continue
        hit_indices = [
            idx for idx, word in enumerate(words) if _overlap(word, int(start), int(end))
        ]
        for position, idx in enumerate(hit_indices):
            prefix = NER_BIO_PREFIX_BEGIN if position == 0 else NER_BIO_PREFIX_INSIDE
            labels[idx] = f"{prefix}{label}"
    return labels


def load_weak_records(path: str | Path) -> list[dict]:
    """Прочитать JSONL weak-датасета."""
    records: list[dict] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def records_to_examples(records: Iterable[dict]) -> list[BioExample]:
    """Превратить weak-записи в BIO-примеры."""
    examples: list[BioExample] = []
    for record in records:
        text = record.get("text") or ""
        words = tokenize_words(text)
        labels = align_labels(words, record.get("spans") or [])
        examples.append(BioExample(words=[word.text for word in words], labels=labels))
    return examples

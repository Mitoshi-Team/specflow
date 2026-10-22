"""Инференс обученной NER-модели: BIO-теги → спаны.

Тяжёлые зависимости (``torch``, ``transformers``) импортируются лениво внутри
``TransformersSpanPredictor.__init__``, чтобы модуль и ``decode_bio`` были
доступны без установленной модели. Декодирование вынесено в чистую функцию
и покрыто тестами.
"""

from __future__ import annotations

from collections.abc import Sequence

from attribute_extractor.constants import (
    DEFAULT_NER_SPAN_MIN_SCORE,
    NER_BIO_OUTSIDE,
    NER_BIO_PREFIX_BEGIN,
    NER_BIO_PREFIX_INSIDE,
    NER_TRAIN_MAX_LENGTH,
)
from attribute_extractor.extractors.ner import NERSpan


def _split_label(label: str) -> tuple[str, str | None]:
    """BIO-метка → (префикс, класс); для ``O`` класс ``None``."""
    if label == NER_BIO_OUTSIDE:
        return NER_BIO_OUTSIDE, None
    for prefix in (NER_BIO_PREFIX_BEGIN, NER_BIO_PREFIX_INSIDE):
        if label.startswith(prefix):
            return prefix, label[len(prefix) :]
    return NER_BIO_OUTSIDE, None


def decode_bio(
    text: str,
    tokens: Sequence[tuple[int, int, str, float]],
) -> list[NERSpan]:
    """Собрать спаны из токенов ``(start, end, label, score)``.

    Смежные (нулевой зазор) и ``I-``-продолжения одной сущности объединяются;
    ``I-`` после чужой/отсутствующей сущности того же класса не склеивает
    соседние значения через пробел (начинает новый спан). Score спана —
    минимум по токенам.
    """
    spans: list[NERSpan] = []
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current is not None:
            spans.append(
                NERSpan(
                    text=text[current["start"] : current["end"]],
                    label=current["label"],
                    start=current["start"],
                    end=current["end"],
                    score=current["score"],
                )
            )
            current = None

    for start, end, label, score in tokens:
        if start == end:
            continue
        prefix, entity = _split_label(label)
        if entity is None:
            flush()
            continue
        if current is not None and current["label"] == entity:
            if start == current["end"]:
                # Нулевой зазор — смежные подслова одного слова («Восстанов»
                # + «ленный»): модель после subword-сегментации не обязана
                # ставить I- на продолжение слова, поэтому склеиваем по
                # фактам смежности, а не по префиксу.
                current["end"] = end
                current["score"] = min(current["score"], score)
                continue
            if prefix == NER_BIO_PREFIX_INSIDE:
                # I- продолжение той же сущности через зазор — слова внутри
                # одного значения («iPhone 12»).
                current["end"] = end
                current["score"] = min(current["score"], score)
                continue
        flush()
        current = {
            "start": start,
            "end": end,
            "label": entity,
            "score": score,
        }
    flush()
    return spans


def filter_spans(
    spans: Sequence[NERSpan],
    min_score: float = DEFAULT_NER_SPAN_MIN_SCORE,
) -> list[NERSpan]:
    """Отсечь спаны ниже порога уверенности (precision-first политика)."""
    return [span for span in spans if span.score >= min_score]


class TransformersSpanPredictor:
    """``SpanPredictor`` поверх обученной token-classification модели."""

    def __init__(
        self,
        model_path: str,
        device: str | None = None,
        max_length: int = NER_TRAIN_MAX_LENGTH,
        min_score: float = DEFAULT_NER_SPAN_MIN_SCORE,
    ) -> None:
        import torch
        from transformers import (
            AutoModelForTokenClassification,
            AutoTokenizer,
        )

        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(model_path)
        self._model = AutoModelForTokenClassification.from_pretrained(model_path)
        self._device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._model.to(self._device)
        self._model.eval()
        self._max_length = max_length
        self._min_score = min_score
        self._id2label = {idx: label for idx, label in self._model.config.id2label.items()}

    def predict(self, text: str) -> list[NERSpan]:
        if not text.strip():
            return []
        encoded = self._tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=self._max_length,
            return_offsets_mapping=True,
        )
        offsets = encoded.pop("offset_mapping")[0].tolist()
        encoded = {key: value.to(self._device) for key, value in encoded.items()}
        with self._torch.no_grad():
            logits = self._model(**encoded).logits[0]
        probabilities = self._torch.softmax(logits, dim=-1)
        scores, ids = probabilities.max(dim=-1)
        tokens: list[tuple[int, int, str, float]] = []
        for (start, end), label_id, score in zip(
            offsets,
            ids.tolist(),
            scores.tolist(),
            strict=True,
        ):
            if start == end:
                continue
            tokens.append((start, end, self._id2label[label_id], float(score)))
        return filter_spans(decode_bio(text, tokens), self._min_score)

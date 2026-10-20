"""NER-экстрактор: пейринг CHARACTERISTIC ↔ PROPERTY и резолв полей (Этапы 4-5).

Модель не входит в сервис: текст на спаны предсказывает инъецированный
``SpanPredictor`` (тяжёлая зависимость подключается на Фазе B, при обучении
модели). Пары «характеристика → значение» резолвятся ``FieldResolver``:
канонический матч даёт код поля, имя вне каталога — slug авто-нового поля
с ``is_new_field=True`` (Этап 5), заблокированные имена отбрасываются.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from attribute_extractor.constants import (
    NER_CHARACTERISTIC_FEATURE_KEY,
    NER_EXTRACTOR_NAME,
    NER_EXTRACTOR_PRIORITY,
    NER_LABEL_CHARACTERISTIC,
    NER_LABEL_PROPERTY,
    NER_PAIR_WINDOW,
)
from attribute_extractor.extractors.base import BaseExtractor
from attribute_extractor.fields import CharacteristicMatch, FieldResolver
from attribute_extractor.grounding import locate_span
from attribute_extractor.preprocessing import normalize_text
from specflow_contracts import (
    AttributeCandidate,
    CategorySchema,
    ExtractionMethod,
    ProductCard,
    Span,
    SpanField,
)


@dataclass
class NERSpan:
    text: str
    label: str
    start: int
    end: int
    score: float


@dataclass
class NERPair:
    characteristic: str
    property: str
    ner_score: float


class SpanPredictor(Protocol):
    """Предсказатель спанов: нормализованный текст карточки → NER-спаны."""

    def predict(self, text: str) -> list[NERSpan]: ...


class NERExtractor(BaseExtractor):
    """Минимальный NER-экстрактор для фокуса (без тяжёлых зависимостей)."""

    name = NER_EXTRACTOR_NAME
    priority = NER_EXTRACTOR_PRIORITY

    def __init__(
        self,
        model_path: str | None = None,
        enabled: bool = True,
        predictor: SpanPredictor | None = None,
        resolver: FieldResolver | None = None,
    ) -> None:
        self.model_path = model_path
        self.enabled = enabled
        self.predictor = predictor
        self._resolver = resolver
        self._loaded = False

    def load(self) -> None:
        # Graceful: без predictor/модели считаем недоступным
        self._loaded = self.predictor is not None or bool(self.model_path)

    def is_available(self) -> bool:
        # Без резолвера пары не превращаются в кандидатов (Этап 5):
        # экстрактор считается недоступным, пайплайн уходит в деградацию.
        return self.enabled and self._loaded and self._resolver is not None

    def extract_pairs(self, spans: Iterable[NERSpan]) -> list[NERPair]:
        """Пейринг: для каждого CHARACTERISTIC ищем ближайший PROPERTY в окне."""
        s_list = list(spans)
        chars = [x for x in s_list if x.label == NER_LABEL_CHARACTERISTIC]
        props = [x for x in s_list if x.label == NER_LABEL_PROPERTY]
        pairs: list[NERPair] = []
        for c in chars:
            best = None
            best_score = -1.0
            for p in props:
                dist = abs(p.start - c.start)
                if dist > NER_PAIR_WINDOW:
                    continue
                # простая эвристика: выше score → лучше
                sc = float(min(c.score, p.score))
                if sc > best_score:
                    best_score = sc
                    best = p
            if best is not None and best_score > 0.0:
                pairs.append(
                    NERPair(
                        characteristic=c.text,
                        property=best.text,
                        ner_score=best_score,
                    )
                )
        return pairs

    def extract(
        self,
        card: ProductCard,
        schema: CategorySchema | None = None,
    ) -> list[AttributeCandidate]:
        resolver = self._resolver
        predictor = self.predictor
        if not self.is_available() or resolver is None or predictor is None:
            return []
        text = normalize_text(card.raw_text)
        candidates: list[AttributeCandidate] = []
        for pair in self.extract_pairs(predictor.predict(text)):
            match = resolver.resolve(pair.characteristic)
            if match.blocked:
                continue
            candidates.append(self._candidate(card, pair, match))
        return candidates

    def _candidate(
        self,
        card: ProductCard,
        pair: NERPair,
        match: CharacteristicMatch,
    ) -> AttributeCandidate:
        value_span = _locate(card, pair.property)
        name_span = _locate(card, pair.characteristic)
        source_spans = [span for span in (value_span, name_span) if span is not None]
        return AttributeCandidate(
            attribute_code=match.matched_code,
            raw_value=pair.property,
            normalized_value=pair.property,
            confidence=pair.ner_score,
            extraction_method=ExtractionMethod.NER,
            is_confirmed_in_text=value_span is not None,
            source_spans=source_spans,
            evidence_text=pair.property,
            ner_score=pair.ner_score,
            match_score=match.match_score,
            is_new_field=match.is_new_field,
            features={NER_CHARACTERISTIC_FEATURE_KEY: pair.characteristic},
        )


def _locate(card: ProductCard, needle: str) -> Span | None:
    """Привязать текст спана к оригинальным title/description (как у правил)."""
    for field, original in (
        (SpanField.TITLE, card.title),
        (SpanField.DESCRIPTION, card.description),
    ):
        if not original:
            continue
        span = locate_span(needle, field, original)
        if span is not None:
            return span
    return None

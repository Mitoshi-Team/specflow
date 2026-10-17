"""NER-экстрактор: пейринг CHARACTERISTIC ↔ PROPERTY в окне, возврат пар с ner_score."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from attribute_extractor.constants import (
    NER_EXTRACTOR_NAME,
    NER_EXTRACTOR_PRIORITY,
    NER_LABEL_CHARACTERISTIC,
    NER_LABEL_PROPERTY,
    NER_PAIR_WINDOW,
)
from attribute_extractor.extractors.base import BaseExtractor
from specflow_contracts import AttributeCandidate, CategorySchema, ProductCard


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


class NERExtractor(BaseExtractor):
    """Минимальный NER-экстрактор для фокуса (без тяжёлых зависимостей)."""

    name = NER_EXTRACTOR_NAME
    priority = NER_EXTRACTOR_PRIORITY

    def __init__(self, model_path: str | None = None, enabled: bool = True) -> None:
        self.model_path = model_path
        self.enabled = enabled
        self._loaded = False

    def load(self) -> None:
        # Graceful: без модели считаем недоступным
        self._loaded = bool(self.model_path)

    def is_available(self) -> bool:
        return self.enabled and self._loaded

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
        return []

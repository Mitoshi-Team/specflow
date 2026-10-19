"""Расчёт уверенности кандидатов по методу извлечения (Этап 10).

Согласно openspec/specs/attribute_extractor.md (Этап 10) уверенность не
взвешивается и не штрафуется по методу: для детерминированных методов
(``structured``/``rule``) она равна константе ``DETERMINISTIC_CONFIDENCE``,
для ``ner`` — модельной оценке ``ner_score``. ``match_score`` в уверенность
не входит — он отражает только качество матча поля.
"""

from __future__ import annotations

from collections.abc import Iterable

from attribute_extractor.constants import DETERMINISTIC_CONFIDENCE, REVIEW_THRESHOLD
from specflow_contracts import AttributeCandidate, ExtractionMethod


class ConfidenceCalculator:
    """Уверенность кандидата как функция метода извлечения.

    Для детерминированных методов уверенность фиксирована и берётся из
    настройки ``Settings.deterministic_confidence``; для NER она равна
    ``ner_score``. Если NER-кандидат пришёл без оценки модели, доверять ему
    нельзя — уверенность опускается в полосу ручной проверки
    (``REVIEW_THRESHOLD``), и по порогам Этапа 10 карточка уходит в
    ``low_confidence``.
    """

    def __init__(self, deterministic_confidence: float = DETERMINISTIC_CONFIDENCE) -> None:
        self._deterministic_confidence = deterministic_confidence

    @property
    def deterministic_confidence(self) -> float:
        """Константа уверенности детерминированных методов."""
        return self._deterministic_confidence

    def candidate_conf(self, candidate: AttributeCandidate) -> float:
        """Уверенность кандидата по его ``extraction_method``."""
        if candidate.extraction_method is ExtractionMethod.NER:
            if candidate.ner_score is None:
                return REVIEW_THRESHOLD
            return candidate.ner_score
        return self._deterministic_confidence

    def apply(self, candidates: Iterable[AttributeCandidate]) -> list[AttributeCandidate]:
        """Проставить уверенность кандидатам, не мутируя исходные объекты.

        Возвращаются новые объекты: последующие этапы (нормализация) могут
        дополнительно понизить уверенность, не влияя на вход.
        """
        return [
            candidate.model_copy(update={"confidence": self.candidate_conf(candidate)})
            for candidate in candidates
        ]

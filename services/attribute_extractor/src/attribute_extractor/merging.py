"""Candidate Merging — объединение кандидатов атрибутов (Этап 4).

Согласно openspec/specs/attribute_extractor.md (Этап 4), кандидаты группируются
по паре ``(attribute_code, normalized_value)``. Внутри группы уверенность
агрегируется взвешенно с учётом подтверждения в тексте:

    conf_agg = (Σ w_m · conf_m · g_m) / (Σ w_m · g_m)

где ``g_m = 1.0`` для подтверждённых кандидатов (``is_confirmed_in_text``) и
``0.0`` иначе. Конфликты (разные значения одного атрибута) разрешаются по
признаку подтверждённости и весу метода; при двух подтверждённых значениях
оба сохраняются с пониженной уверенностью и признаком конфликта.
"""

from attribute_extractor.constants import (
    CONFLICT_FEATURE_KEY,
    CONFLICTING_VALUES_PENALTY,
    DEFAULT_METHOD_WEIGHT,
    DEFAULT_METHOD_WEIGHTS,
    GROUNDING_FACTOR_CONFIRMED,
    GROUNDING_FACTOR_UNCONFIRMED,
    MERGED_METHOD,
)
from specflow_contracts import AttributeCandidate, ExtractionMethod, Span
from specflow_contracts.constants import MAX_CONFIDENCE, MIN_CONFIDENCE


def _clamp(value: float) -> float:
    """Ограничить уверенность допустимым диапазоном."""
    return max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, value))


class CandidateMerger:
    """Объединяет кандидатов атрибутов и разрешает конфликты (Этап 4)."""

    def __init__(
        self,
        method_weights: dict[str, float] | None = None,
        *,
        conflicting_values_penalty: float = CONFLICTING_VALUES_PENALTY,
        default_method_weight: float = DEFAULT_METHOD_WEIGHT,
    ) -> None:
        self._method_weights = (
            dict(method_weights) if method_weights is not None else dict(DEFAULT_METHOD_WEIGHTS)
        )
        self._conflicting_values_penalty = conflicting_values_penalty
        self._default_method_weight = default_method_weight

    def merge(self, candidates: list[AttributeCandidate]) -> list[AttributeCandidate]:
        """Объединить кандидатов, вернув по одному значению на атрибут (с учётом конфликтов)."""
        groups: dict[tuple[str, str], list[AttributeCandidate]] = {}
        for candidate in candidates:
            key = (candidate.attribute_code, candidate.normalized_value)
            groups.setdefault(key, []).append(candidate)

        merged = [self._merge_group(group) for group in groups.values()]
        return self._resolve_conflicts(merged)

    def _merge_group(self, candidates: list[AttributeCandidate]) -> AttributeCandidate:
        """Слить кандидатов одной пары (attribute_code, normalized_value)."""
        best = max(candidates, key=lambda candidate: self._rank(candidate))
        confidence = self._aggregate_confidence(candidates)
        is_confirmed = any(candidate.is_confirmed_in_text for candidate in candidates)
        methods = {candidate.extraction_method for candidate in candidates}
        method = next(iter(methods)) if len(methods) == 1 else ExtractionMethod(MERGED_METHOD)
        features: dict[str, object] = {}
        for candidate in candidates:
            if candidate.features:
                features.update(candidate.features)
        return AttributeCandidate(
            attribute_code=best.attribute_code,
            raw_value=best.raw_value,
            normalized_value=best.normalized_value,
            confidence=confidence,
            extraction_method=method,
            is_confirmed_in_text=is_confirmed,
            source_spans=self._merge_spans(candidates),
            evidence_text=best.evidence_text,
            features=features or None,
        )

    def _aggregate_confidence(self, candidates: list[AttributeCandidate]) -> float:
        """Взвешенно агрегировать уверенность с учётом grounding-множителя."""
        weighted = confirmed = 0.0
        for candidate in candidates:
            weight = self._method_weight(candidate)
            factor = (
                GROUNDING_FACTOR_CONFIRMED
                if candidate.is_confirmed_in_text
                else GROUNDING_FACTOR_UNCONFIRMED
            )
            weighted += weight * candidate.confidence * factor
            confirmed += weight * factor
        if confirmed > 0:
            return _clamp(weighted / confirmed)
        # Никто не подтверждён: агрегируем без grounding-множителя (g_m = 1).
        total = sum(self._method_weight(candidate) for candidate in candidates)
        if total > 0:
            weighted = sum(
                self._method_weight(candidate) * candidate.confidence for candidate in candidates
            )
            return _clamp(weighted / total)
        return _clamp(candidates[0].confidence)

    def _resolve_conflicts(self, candidates: list[AttributeCandidate]) -> list[AttributeCandidate]:
        """Оставить по одному значению на атрибут, разрешив конфликты (Этап 4)."""
        by_code: dict[str, list[AttributeCandidate]] = {}
        for candidate in candidates:
            by_code.setdefault(candidate.attribute_code, []).append(candidate)

        resolved: list[AttributeCandidate] = []
        for group in by_code.values():
            if len(group) == 1:
                resolved.append(group[0])
                continue
            grounded = [candidate for candidate in group if candidate.is_confirmed_in_text]
            if len(grounded) == 1:
                resolved.append(grounded[0])
            elif len(grounded) > 1:
                resolved.extend(self._flag_conflict(candidate) for candidate in grounded)
            else:
                resolved.append(max(group, key=lambda candidate: self._rank(candidate)))
        return resolved

    def _flag_conflict(self, candidate: AttributeCandidate) -> AttributeCandidate:
        """Понизить уверенность конфликтующего кандидата и отметить признак."""
        features = dict(candidate.features or {})
        features[CONFLICT_FEATURE_KEY] = True
        return candidate.model_copy(
            update={
                "confidence": _clamp(candidate.confidence - self._conflicting_values_penalty),
                "features": features,
            }
        )

    def _rank(self, candidate: AttributeCandidate) -> tuple[float, float, int]:
        """Ключ ранжирования: подтверждённость, вес метода, уверенность."""
        return (
            GROUNDING_FACTOR_CONFIRMED if candidate.is_confirmed_in_text else 0.0,
            self._method_weight(candidate),
            candidate.confidence,
        )

    def _method_weight(self, candidate: AttributeCandidate) -> float:
        """Вес метода кандидата (с запасным значением по умолчанию)."""
        return self._method_weights.get(
            candidate.extraction_method.value, self._default_method_weight
        )

    @staticmethod
    def _merge_spans(candidates: list[AttributeCandidate]) -> list[Span]:
        """Объединить source_spans кандидатов без дубликатов."""
        spans: list[Span] = []
        seen: set[tuple[object, ...]] = set()
        for candidate in candidates:
            for span in candidate.source_spans:
                key = (span.field, span.text, span.start, span.end)
                if key not in seen:
                    seen.add(key)
                    spans.append(span)
        return spans

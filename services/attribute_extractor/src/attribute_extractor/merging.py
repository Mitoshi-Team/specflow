"""Candidate Merging — объединение кандидатов атрибутов.

Согласно openspec/specs/attribute_extractor.md кандидаты группируются по паре
``(attribute_code, normalized_value)``; внутри группы берётся кандидат с
максимальной уверенностью. При разных ``normalized_value`` для одного кода
остаётся кандидат с максимальным confidence, а в ``features`` проставляется
``conflict`` (downstream-этап выставляет ``needs_review``). Никаких весов
методов, штрафов и взвешенной агрегации — уверенность методов уже
детерминирована на этапах извлечения.
"""

from attribute_extractor.constants import CONFLICT_FEATURE_KEY
from specflow_contracts import AttributeCandidate, Span
from specflow_contracts.constants import MAX_CONFIDENCE, MIN_CONFIDENCE


def _clamp(value: float) -> float:
    """Ограничить уверенность допустимым диапазоном."""
    return max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, value))


class CandidateMerger:
    """Объединяет кандидатов атрибутов и разрешает конфликты."""

    def merge(self, candidates: list[AttributeCandidate]) -> list[AttributeCandidate]:
        """Слить дубли пар (code, value) и оставить одно значение на атрибут."""
        groups: dict[tuple[str, str], list[AttributeCandidate]] = {}
        for candidate in candidates:
            groups.setdefault((candidate.attribute_code, candidate.normalized_value), []).append(
                candidate
            )

        merged = [self._merge_group(group) for group in groups.values()]
        return self._resolve_conflicts(merged)

    @staticmethod
    def _merge_group(candidates: list[AttributeCandidate]) -> AttributeCandidate:
        """Слить кандидатов одной пары (attribute_code, normalized_value): max confidence."""
        best = max(candidates, key=lambda candidate: candidate.confidence)
        is_confirmed = any(candidate.is_confirmed_in_text for candidate in candidates)
        features: dict[str, object] = {}
        for candidate in candidates:
            if candidate.features:
                features.update(candidate.features)
        return AttributeCandidate(
            attribute_code=best.attribute_code,
            raw_value=best.raw_value,
            normalized_value=best.normalized_value,
            confidence=_clamp(max(candidate.confidence for candidate in candidates)),
            extraction_method=best.extraction_method,
            is_confirmed_in_text=is_confirmed,
            source_spans=CandidateMerger._merge_spans(candidates),
            evidence_text=best.evidence_text,
            ner_score=best.ner_score,
            match_score=best.match_score,
            is_new_field=best.is_new_field,
            features=features or None,
        )

    @staticmethod
    def _resolve_conflicts(candidates: list[AttributeCandidate]) -> list[AttributeCandidate]:
        """Оставить одно значение на атрибут: max confidence + флаг конфликта."""
        by_code: dict[str, list[AttributeCandidate]] = {}
        for candidate in candidates:
            by_code.setdefault(candidate.attribute_code, []).append(candidate)

        resolved: list[AttributeCandidate] = []
        for group in by_code.values():
            if len(group) == 1:
                resolved.append(group[0])
                continue
            best = max(group, key=lambda candidate: candidate.confidence)
            features = dict(best.features or {})
            features[CONFLICT_FEATURE_KEY] = True
            resolved.append(best.model_copy(update={"features": features}))
        return resolved

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

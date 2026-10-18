"""Candidate Merging — объединение кандидатов атрибутов.

Согласно openspec/specs/attribute_extractor.md кандидаты группируются по
``attribute_code`` (значение в ключ группировки не входит); внутри группы
остаётся кандидат с максимальной уверенностью, его ``normalized_value``
становится значением атрибута. Спаны и features объединяются только от
кандидатов с тем же значением, что и у победителя. Если в группе есть
кандидаты с другим ``normalized_value`` — в ``features`` проставляется
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
        """Оставить одного кандидата на ``attribute_code``: max confidence + флаг конфликта."""
        groups: dict[str, list[AttributeCandidate]] = {}
        for candidate in candidates:
            groups.setdefault(candidate.attribute_code, []).append(candidate)
        return [self._merge_group(group) for group in groups.values()]

    @staticmethod
    def _merge_group(candidates: list[AttributeCandidate]) -> AttributeCandidate:
        """Слить кандидатов одного ``attribute_code``: max confidence, спаны/ features
        только от кандидатов с тем же значением, что и у победителя."""
        best = max(candidates, key=lambda candidate: candidate.confidence)
        same_value = [
            candidate
            for candidate in candidates
            if candidate.normalized_value == best.normalized_value
        ]
        has_conflict = len(same_value) < len(candidates)

        is_confirmed = any(candidate.is_confirmed_in_text for candidate in same_value)
        features: dict[str, object] = {}
        for candidate in same_value:
            if candidate.features:
                features.update(candidate.features)
        if has_conflict:
            features[CONFLICT_FEATURE_KEY] = True

        return AttributeCandidate(
            attribute_code=best.attribute_code,
            raw_value=best.raw_value,
            normalized_value=best.normalized_value,
            confidence=_clamp(best.confidence),
            extraction_method=best.extraction_method,
            is_confirmed_in_text=is_confirmed,
            source_spans=CandidateMerger._merge_spans(same_value),
            evidence_text=best.evidence_text,
            ner_score=best.ner_score,
            match_score=best.match_score,
            is_new_field=best.is_new_field,
            features=features or None,
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

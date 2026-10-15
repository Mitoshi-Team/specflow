"""Grounding Validation — обязательная проверка подтверждения значений (Этап 5).

Согласно openspec/specs/attribute_extractor.md (Этап 5), все финальные
кандидаты должны быть подтверждены в исходном тексте карточки. Проверяется
``evidence_text`` или ключевые токены значения: точное/нормализованное
подстроковое совпадение с учётом регистра, пробелов, чисел (``6,7`` ↔ ``6.7``)
и единиц измерения (``ГБ`` ↔ ``GB``). Кандидаты без подтверждения отбрасываются.
"""

import re

from attribute_extractor.constants import (
    DECIMAL_COMMA_PATTERN,
    GROUNDING_UNIT_ALIASES,
    INCH_SYMBOL_PATTERN,
    WHITESPACE_PATTERN,
)
from attribute_extractor.preprocessing import normalize_text
from specflow_contracts import AttributeCandidate, ProductCard, Span, SpanField

_INCH_RE = re.compile(INCH_SYMBOL_PATTERN)
_DECIMAL_COMMA_RE = re.compile(DECIMAL_COMMA_PATTERN)
_WHITESPACE_RE = re.compile(WHITESPACE_PATTERN)


def _build_unit_re() -> re.Pattern[str]:
    """Собрать регулярное выражение для замены синонимов единиц измерения.

    Более длинные алиасы идут первыми, чтобы ``дюймов`` не перехватывался
    ``дюйм``; для словесных алиасов добавляются границы по ``\\w``.
    """
    parts = []
    for alias in sorted(GROUNDING_UNIT_ALIASES, key=len, reverse=True):
        escaped = re.escape(alias)
        if alias[0].isalnum() and alias[-1].isalnum():
            parts.append(rf"(?<!\w){escaped}(?!\w)")
        else:
            parts.append(escaped)
    return re.compile("|".join(parts))


_UNIT_RE = _build_unit_re()


def _canonicalize(text: str) -> str:
    """Привести текст к каноническому виду для сопоставления при grounding.

    Регистр, пробелы и кавычки нормализуются; десятичная запятая заменяется
    на точку, дюймовый символ — на ``in``, синонимы единиц — на канонические.
    """
    if not text:
        return ""
    canonical = normalize_text(text).lower()
    canonical = _INCH_RE.sub(r"\1 in", canonical)
    canonical = _DECIMAL_COMMA_RE.sub(".", canonical)
    canonical = _UNIT_RE.sub(lambda match: GROUNDING_UNIT_ALIASES[match.group(0)], canonical)
    return _WHITESPACE_RE.sub(" ", canonical).strip()


class GroundingValidator:
    """Проверяет, что кандидаты подтверждены текстом карточки (Этап 5)."""

    def is_grounded(self, candidate: AttributeCandidate, card: ProductCard) -> bool:
        """Подтверждён ли кандидат в тексте карточки."""
        return self._find_span(candidate, self._searchable_fields(card)) is not None

    def filter(
        self, candidates: list[AttributeCandidate], card: ProductCard
    ) -> list[AttributeCandidate]:
        """Hard filter: оставить только подтверждённые кандидаты (Этап 5).

        Проставляет ``is_confirmed_in_text=True`` и, если у кандидата нет
        ``source_spans``, добавляет span найденного упоминания.
        """
        fields = self._searchable_fields(card)
        confirmed: list[AttributeCandidate] = []
        for candidate in candidates:
            span = self._find_span(candidate, fields)
            if span is None:
                continue
            updates: dict[str, object] = {"is_confirmed_in_text": True}
            if not candidate.source_spans:
                updates["source_spans"] = [span]
            confirmed.append(candidate.model_copy(update=updates))
        return confirmed

    def _searchable_fields(self, card: ProductCard) -> list[tuple[SpanField, str, str, str]]:
        """Вернуть поля карточки: (field, оригинал, канонический, нормализованный)."""
        seller_text = str(card.seller_attributes) if card.seller_attributes else None
        raw_fields = (
            (SpanField.TITLE, card.title),
            (SpanField.DESCRIPTION, card.description),
            (SpanField.SELLER_ATTRIBUTES, seller_text),
        )
        return [
            (field, text, _canonicalize(text), normalize_text(text).lower())
            for field, text in raw_fields
            if text
        ]

    def _find_span(
        self, candidate: AttributeCandidate, fields: list[tuple[SpanField, str, str, str]]
    ) -> Span | None:
        """Найти подтверждающий span: по evidence_text, затем по токенам значения."""
        evidence = candidate.evidence_text
        if evidence:
            evidence_canonical = _canonicalize(evidence)
            if evidence_canonical:
                for field, original, canonical, _ in fields:
                    if evidence_canonical in canonical:
                        return self._locate_span(evidence, field, original) or Span(
                            field=field, text=evidence
                        )
            evidence_normalized = normalize_text(evidence).lower()
            if evidence_normalized:
                for field, original, _, normalized in fields:
                    if evidence_normalized in normalized:
                        return self._locate_span(evidence, field, original) or Span(
                            field=field, text=evidence
                        )
        value = candidate.normalized_value or candidate.raw_value
        tokens = _canonicalize(value).split()
        if tokens:
            for field, _, canonical, _ in fields:
                field_tokens = set(canonical.split())
                if all(token in field_tokens for token in tokens):
                    return Span(field=field, text=value)
        return None

    @staticmethod
    def _locate_span(needle: str, field: SpanField, original: str) -> Span | None:
        """Найти точные позиции ``needle`` в оригинальном тексте (без учёта регистра)."""
        index = original.lower().find(needle.lower())
        if index < 0:
            return None
        return Span(
            field=field,
            text=original[index : index + len(needle)],
            start=index,
            end=index + len(needle),
        )

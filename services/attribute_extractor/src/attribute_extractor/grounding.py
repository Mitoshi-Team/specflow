"""Grounding Validation — обязательная проверка подтверждения значений (Этап 9).

Согласно openspec/specs/attribute_extractor.md (Этап 9), все финальные
кандидаты должны быть подтверждены в исходном тексте карточки: заголовке и
определении — это вход пайплайна (seller-атрибуты входом не являются).
Проверяется ``evidence_text`` или ключевые токены значения: точное/нормализованное
подстроковое совпадение с учётом регистра, пробелов, чисел (``6,7`` ↔ ``6.7``),
единиц измерения (``ГБ`` ↔ ``GB``, ``128GB`` ↔ ``128 gb``) и синонимов цветов
(``Black`` подтверждает канон «черный»). Кандидаты без подтверждения
отбрасываются.
"""

import html
import re

from attribute_extractor.constants import (
    COLOR_SYNONYMS,
    DASH_NORMALIZATION,
    DECIMAL_COMMA_PATTERN,
    DIGIT_LETTER_PATTERN,
    DOT_SEPARATOR_PATTERN,
    GROUNDING_UNIT_ALIASES,
    HTML_TAG_PATTERN,
    INCH_SYMBOL_PATTERN,
    NUMBER_WORD_HYPHEN_PATTERN,
    TOKEN_SEPARATOR_PATTERN,
    WHITESPACE_PATTERN,
)
from attribute_extractor.preprocessing import normalize_text
from specflow_contracts import AttributeCandidate, ProductCard, Span, SpanField

_INCH_RE = re.compile(INCH_SYMBOL_PATTERN)
_DECIMAL_COMMA_RE = re.compile(DECIMAL_COMMA_PATTERN)
_DIGIT_LETTER_RE = re.compile(DIGIT_LETTER_PATTERN)
_DOT_RE = re.compile(DOT_SEPARATOR_PATTERN)
_HYPHEN_RE = re.compile(NUMBER_WORD_HYPHEN_PATTERN)
_SEPARATOR_RE = re.compile(TOKEN_SEPARATOR_PATTERN)
_HTML_TAG_RE = re.compile(HTML_TAG_PATTERN)
_WHITESPACE_RE = re.compile(WHITESPACE_PATTERN)


def locate_span(needle: str, field: SpanField, original: str) -> Span | None:
    """Найти точные позиции ``needle`` в оригинальном тексте (без учёта регистра).

    Публичная функция: переиспользуется экстракторами (RuleExtractor) для
    привязки найденного значения к исходным offset'ам карточки.
    """
    index = original.lower().find(needle.lower())
    if index < 0:
        return None
    return Span(
        field=field,
        text=original[index : index + len(needle)],
        start=index,
        end=index + len(needle),
    )


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

    Регистр, пробелы и кавычки нормализуются, ``ё`` сворачивается в ``е``
    (каноническая форма значений вроде «черный»), HTML-сущности и теги
    разворачиваются/вырезаются, типографские тире приводятся к ASCII-дефису,
    десятичная запятая заменяется на точку, дюймовый символ — на ``in``.
    Слипшиеся токены разлипаются: граница «цифра → буква» (``128GB`` →
    ``128 gb``, ``16Гб`` → ``16 гб``), несистемные точки не отделяются от
    десятичных (``50 in.`` → ``50 in``, ``6.7`` остаётся), дефис между числом
    и словом — на пробел (``6.7-дюймовый``), слэши и запятые-разделители —
    на пробел (``i7-13620H/16Гб``), синонимы единиц — на канонические.
    """
    if not text:
        return ""
    canonical = html.unescape(normalize_text(text)).lower().replace("ё", "е")
    canonical = _HTML_TAG_RE.sub(" ", canonical)
    for dash, replacement in DASH_NORMALIZATION.items():
        canonical = canonical.replace(dash, replacement)
    canonical = _INCH_RE.sub(r"\1 in ", canonical)
    canonical = _DECIMAL_COMMA_RE.sub(".", canonical)
    canonical = _DIGIT_LETTER_RE.sub(" ", canonical)
    canonical = _DOT_RE.sub(" ", canonical)
    canonical = _HYPHEN_RE.sub(" ", canonical)
    canonical = _SEPARATOR_RE.sub(" ", canonical)
    canonical = _UNIT_RE.sub(lambda match: GROUNDING_UNIT_ALIASES[match.group(0)], canonical)
    return _WHITESPACE_RE.sub(" ", canonical).strip()


class GroundingValidator:
    """Проверяет, что кандидаты подтверждены текстом карточки (Этап 9)."""

    def is_grounded(self, candidate: AttributeCandidate, card: ProductCard) -> bool:
        """Подтверждён ли кандидат в тексте карточки."""
        return self._find_span(candidate, self._searchable_fields(card)) is not None

    def filter(
        self, candidates: list[AttributeCandidate], card: ProductCard
    ) -> list[AttributeCandidate]:
        """Hard filter: оставить только подтверждённые кандидаты (Этап 9).

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
        """Вернуть поля карточки: (field, оригинал, канонический, нормализованный).

        Seller-атрибуты не участвуют: вход пайплайна — только заголовок и
        описание (характеристики извлекаются из свободного текста).
        """
        raw_fields = (
            (SpanField.TITLE, card.title),
            (SpanField.DESCRIPTION, card.description),
        )
        return [
            (field, text, _canonicalize(text), normalize_text(text).lower())
            for field, text in raw_fields
            if text
        ]

    def _value_token_sets(self, candidate: AttributeCandidate, value: str) -> list[list[str]]:
        """Варианты token-наборов значения: канон + синонимы цветов (``Black``)."""
        sets = [_canonicalize(value).split()]
        if candidate.attribute_code == "color":
            canonical = _canonicalize(value)
            sets += [
                _canonicalize(synonym).split() for synonym in COLOR_SYNONYMS.get(canonical, ())
            ]
        return [tokens for tokens in sets if tokens]

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
                        return locate_span(evidence, field, original) or Span(
                            field=field, text=evidence
                        )
            evidence_normalized = normalize_text(evidence).lower()
            if evidence_normalized:
                for field, original, _, normalized in fields:
                    if evidence_normalized in normalized:
                        return locate_span(evidence, field, original) or Span(
                            field=field, text=evidence
                        )
        value = candidate.normalized_value or candidate.raw_value
        for field, _, canonical, _ in fields:
            field_tokens = set(canonical.split())
            if any(
                all(token in field_tokens for token in tokens)
                for tokens in self._value_token_sets(candidate, value)
            ):
                return Span(field=field, text=value)
        return None

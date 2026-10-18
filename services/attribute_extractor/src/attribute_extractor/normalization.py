"""Нормализация значений атрибутов на базе справочников (Этап 6).

Согласно openspec/specs/attribute_extractor.md (Этап 6), значение приводится к
канонической форме: базовая очистка (trim, пробелы, кавычки, дефисы), регистр
(бренды/enum из справочников), синонимы, унификация и (опционально) конверсия
единиц измерения, форматирование чисел и валидация enum по ``vocab``.

Справочники передаются через :class:`ReferenceCatalog`. Если enum-значение не
сопоставлено со словарём: при ``enum_strict=true`` кандидат отбрасывается
(возвращается ``None``), иначе помечается признаком ``enum_out_of_vocab`` (штраф
применяется на этапе скоринга, Этап 7).
"""

from __future__ import annotations

import re

from attribute_extractor.constants import (
    CANONICAL_UNIT_ALIASES,
    DASH_NORMALIZATION,
    DECIMAL_SEPARATOR,
    DEFAULT_UNIT_CONVERSION_ENABLED,
    ENUM_OUT_OF_VOCAB_FEATURE_KEY,
    NUMBER_WITH_UNIT_PATTERN,
)
from attribute_extractor.preprocessing import normalize_text
from attribute_extractor.references import (
    AttributeVocab,
    ReferenceCatalog,
    build_default_catalog,
)
from specflow_contracts import (
    Attribute,
    AttributeCandidate,
    AttributeValueType,
    CategorySchema,
)

_NUMBER_RE = re.compile(NUMBER_WITH_UNIT_PATTERN)


def _basic_normalize(text: str) -> str:
    """Базовая очистка: пробелы, кавычки, мусорные символы и дефисы."""
    normalized = normalize_text(text)
    for source, target in DASH_NORMALIZATION.items():
        normalized = normalized.replace(source, target)
    return normalized.strip()


def parse_number(text: str) -> float:
    """Разобрать число с запятой или точкой в качестве разделителя.

    Публичная функция: переиспользуется экстракторами (RuleExtractor) для
    форматирования чисел в ``normalized_value``.
    """
    return float(text.replace(",", "."))


def format_number(value: float) -> str:
    """Отформатировать число: без лишних нулей, с каноническим разделителем.

    Публичная функция: единый формат чисел для нормализации и правил.
    """
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    if text in ("", "-"):
        text = "0"
    return text.replace(".", DECIMAL_SEPARATOR)


def _canonical_unit(unit: str) -> str:
    """Унифицировать сокращение единицы измерения."""
    if not unit:
        return ""
    return CANONICAL_UNIT_ALIASES.get(unit.casefold(), unit)


class ValueNormalizer:
    """Приводит значения кандидатов к канонической форме по справочникам (Этап 6)."""

    def __init__(
        self,
        catalog: ReferenceCatalog | None = None,
        *,
        unit_conversion_enabled: bool = DEFAULT_UNIT_CONVERSION_ENABLED,
        enum_strict: bool = False,
        title_case_enabled: bool = False,
    ) -> None:
        self._catalog = catalog if catalog is not None else build_default_catalog()
        self._unit_conversion_enabled = unit_conversion_enabled
        self._enum_strict = enum_strict
        self._title_case_enabled = title_case_enabled

    @property
    def catalog(self) -> ReferenceCatalog:
        """Справочники, используемые нормализатором."""
        return self._catalog

    def normalize(
        self, candidate: AttributeCandidate, attribute: Attribute | None = None
    ) -> AttributeCandidate | None:
        """Нормализовать значение кандидата.

        Возвращает обновлённого кандидата или ``None``, если значение отброшено
        (enum вне словаря при ``enum_strict=true``).
        """
        source = candidate.normalized_value or candidate.raw_value
        value = _basic_normalize(source)
        vocab = self._catalog.attribute_vocab(candidate.attribute_code)
        value_type = attribute.value_type if attribute is not None else None

        out_of_vocab = False
        if value_type is AttributeValueType.ENUM:
            resolved = vocab.resolve(value) if vocab is not None else None
            if resolved is not None:
                value = resolved
            elif self._enum_strict:
                return None
            else:
                out_of_vocab = True
        elif value_type is AttributeValueType.NUMBER:
            value = self._normalize_number(value)
        elif value_type is AttributeValueType.UNIT_VALUE:
            value = self._normalize_unit_value(
                value, candidate.attribute_code, attribute.unit if attribute else None
            )
        else:
            value = self._normalize_text_value(value, vocab)

        features = dict(candidate.features or {})
        if out_of_vocab:
            features[ENUM_OUT_OF_VOCAB_FEATURE_KEY] = True
        return candidate.model_copy(
            update={"normalized_value": value, "features": features or None}
        )

    def normalize_all(
        self, candidates: list[AttributeCandidate], schema: CategorySchema | None = None
    ) -> list[AttributeCandidate]:
        """Нормализовать список кандидатов в рамках схемы категории."""
        attributes: dict[str, Attribute] = {}
        if schema is not None:
            for attribute in (*schema.required_attributes, *schema.optional_attributes):
                attributes[attribute.code] = attribute
        normalized: list[AttributeCandidate] = []
        for candidate in candidates:
            result = self.normalize(candidate, attributes.get(candidate.attribute_code))
            if result is not None:
                normalized.append(result)
        return normalized

    def _normalize_text_value(self, value: str, vocab: AttributeVocab | None) -> str:
        """Нормализовать строковое значение: синонимы, бренд, регистр."""
        if vocab is not None:
            resolved = vocab.resolve(value)
            if resolved is not None:
                return resolved
        brand_vocab = self._catalog.brand_vocab
        if brand_vocab is not None:
            resolved = brand_vocab.resolve(value)
            if resolved is not None:
                return resolved
        if self._title_case_enabled:
            return value.title()
        return value

    @staticmethod
    def _normalize_number(value: str) -> str:
        """Нормализовать числовое значение к единому формату."""
        try:
            number = parse_number(value.replace(" ", ""))
        except ValueError:
            return value
        return format_number(number)

    def _normalize_unit_value(self, value: str, attribute_code: str, unit: str | None) -> str:
        """Нормализовать значение «число + единица» и (опц.) сконвертировать единицу."""
        match = _NUMBER_RE.match(value)
        if match is None:
            return value
        first = parse_number(match.group("first"))
        second = match.group("second")
        secondary = parse_number(second) if second is not None else None
        canonical_unit = _canonical_unit(match.group("unit").strip())

        if self._unit_conversion_enabled and unit and canonical_unit and canonical_unit != unit:
            rule = self._catalog.unit_rule(attribute_code)
            if rule is not None and canonical_unit in rule.conversions and rule.to_unit == unit:
                factor = rule.conversions[canonical_unit]
                first *= factor
                if secondary is not None:
                    secondary *= factor
                canonical_unit = unit

        suffix = f" {canonical_unit}" if canonical_unit else ""
        if secondary is not None:
            return f"{format_number(first)}-{format_number(secondary)}{suffix}"
        return f"{format_number(first)}{suffix}"

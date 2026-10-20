"""Справочники (справочные данные) пайплайна извлечения атрибутов.

Согласно domain-model.md (§3.8) и architecture.md (§4.6), справочники
(AttributeVocab, UnitRule, BrandVocab) хранятся в репозитории и версионируются,
а нормализация значений (Этап 6) выполняется на их базе. ``ReferenceCatalog`` —
in-memory реестр справочников, наследуемый нормализатором значений.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from attribute_extractor.constants import DEFAULT_BRAND_VOCAB_PATH, DEFAULT_VOCAB_VERSION

logger = logging.getLogger(__name__)


class AttributeVocab(BaseModel):
    """Справочник значений атрибута: канонические значения и синонимы.

    Соответствует сущности ``AttributeVocab`` из domain-model.md: используется
    для нормализации и валидации enum-значений.
    """

    attribute_code: str
    canonical_values: list[str] = Field(default_factory=list)
    synonyms_map: dict[str, str] = Field(default_factory=dict)
    unit_mappings: dict[str, str] = Field(default_factory=dict)
    version: str = DEFAULT_VOCAB_VERSION

    def resolve(self, value: str) -> str | None:
        """Сопоставить значение с каноническим: сначала точное, затем синонимы."""
        key = value.casefold().strip()
        if not key:
            return None
        for canonical in self.canonical_values:
            if canonical.casefold() == key:
                return canonical
        if key in self.synonyms_map:
            return self.synonyms_map[key]
        for alias, canonical in self.synonyms_map.items():
            if alias.casefold() == key:
                return canonical
        return None


class UnitRule(BaseModel):
    """Правило приведения единиц измерения для атрибута (domain-model.md §3.8).

    ``conversions`` сопоставляет каноническую единицу-источник коэффициенту
    пересчёта в ``to_unit``. Синонимы (сокращения) унифицируются отдельно по
    ``CANONICAL_UNIT_ALIASES``; здесь задаётся именно конверсия между единицами.
    """

    attribute_code: str
    to_unit: str
    conversions: dict[str, float] = Field(default_factory=dict)
    version: str = DEFAULT_VOCAB_VERSION


class BrandVocab(BaseModel):
    """Словарь брендов: канонические имена, алиасы и стоп-слова (domain-model.md §3.8)."""

    names: list[str] = Field(default_factory=list)
    aliases: dict[str, str] = Field(default_factory=dict)
    stopwords: list[str] = Field(default_factory=list)
    version: str = DEFAULT_VOCAB_VERSION

    def resolve(self, value: str) -> str | None:
        """Сопоставить значение с каноническим именем бренда."""
        key = value.casefold().strip()
        if not key or key in self._stopwords_set():
            return None
        for name in self.names:
            if name.casefold() == key:
                return name
        if key in self.aliases:
            return self.aliases[key]
        for alias, name in self.aliases.items():
            if alias.casefold() == key:
                return name
        return None

    def _stopwords_set(self) -> set[str]:
        return {word.casefold() for word in self.stopwords}


class ReferenceCatalog:
    """In-memory реестр справочников, на базе которого работает нормализация."""

    def __init__(self, *, version: str = DEFAULT_VOCAB_VERSION) -> None:
        self._attribute_vocabs: dict[str, AttributeVocab] = {}
        self._unit_rules: dict[str, UnitRule] = {}
        self._brand_vocab: BrandVocab | None = None
        self._version = version

    @property
    def version(self) -> str:
        """Версия справочников (используется в трассировке)."""
        return self._version

    def register_attribute_vocab(self, vocab: AttributeVocab) -> None:
        """Зарегистрировать (или заменить) справочник атрибута."""
        self._attribute_vocabs[vocab.attribute_code] = vocab

    def register_unit_rule(self, rule: UnitRule) -> None:
        """Зарегистрировать (или заменить) правило единиц измерения."""
        self._unit_rules[rule.attribute_code] = rule

    def set_brand_vocab(self, vocab: BrandVocab) -> None:
        """Установить словарь брендов."""
        self._brand_vocab = vocab

    def attribute_vocab(self, attribute_code: str) -> AttributeVocab | None:
        """Вернуть справочник атрибута или ``None``."""
        return self._attribute_vocabs.get(attribute_code)

    def unit_rule(self, attribute_code: str) -> UnitRule | None:
        """Вернуть правило единиц измерения для атрибута или ``None``."""
        return self._unit_rules.get(attribute_code)

    @property
    def brand_vocab(self) -> BrandVocab | None:
        """Вернуть словарь брендов или ``None``."""
        return self._brand_vocab


def build_default_catalog() -> ReferenceCatalog:
    """Собрать справочники по умолчанию.

    В репозитории пока нет наполнения справочников, поэтому возвращается пустой
    каталог с версией по умолчанию; наполнение — задача MLOps-контура.
    """
    return ReferenceCatalog()


def load_brand_vocab(path: str | Path = DEFAULT_BRAND_VOCAB_PATH) -> BrandVocab | None:
    """Загрузить бренд-словарь из версонируемого ассета.

    Ассет собирается ``scripts/build_brand_vocab.py`` и хранится в репозитории
    (domain-model.md §3.8). Отсутствие файла — штатная ситуация при первом
    прогоне: возвращает ``None``, экстрактор работает без брендовых правил.
    Битый или недоступный ассет деградирует так же (предсказуемое поведение
    внешней зависимости), но с ERROR-логом: порча файла не должна ронять
    сборку реестра (``build_default_registry`` → старт сервиса), однако и не
    должна пройти молча.
    """
    try:
        with Path(path).open(encoding="utf-8") as file:
            return BrandVocab.model_validate(json.load(file))
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError):
        logger.exception("Бренд-словарь в %s не загрузился; работаем без брендовых правил", path)
        return None

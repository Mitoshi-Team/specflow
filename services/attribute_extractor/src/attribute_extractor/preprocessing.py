"""Препроцессинг карточки (Этап 0 пайплайна извлечения атрибутов).

Согласно openspec/specs/attribute_extractor.md (Этап 0): сбор ``raw_text``,
нормализация текста, автоопределение языка, базовая токенизация и резолв
``CategorySchema`` с fallback на generic-схему.
"""

import re
from collections.abc import Iterable

from pydantic import BaseModel

from attribute_extractor.constants import (
    CYRILLIC_LETTER_PATTERN,
    DEFAULT_REMOVE_JUNK_CHARS,
    GENERIC_CATEGORY,
    GENERIC_SCHEMA_VERSION,
    JUNK_CHARS_PATTERN,
    LANGUAGE_EN,
    LANGUAGE_MIXED,
    LANGUAGE_MIXED_MIN_SHARE,
    LANGUAGE_RU,
    LANGUAGE_UNKNOWN,
    LATIN_LETTER_PATTERN,
    QUOTE_NORMALIZATION,
    WHITESPACE_PATTERN,
)
from specflow_contracts import CategorySchema, ProductCard

_JUNK_RE = re.compile(JUNK_CHARS_PATTERN)
_WHITESPACE_RE = re.compile(WHITESPACE_PATTERN)
_CYRILLIC_RE = re.compile(CYRILLIC_LETTER_PATTERN)
_LATIN_RE = re.compile(LATIN_LETTER_PATTERN)


def normalize_text(text: str, *, remove_junk_chars: bool = DEFAULT_REMOVE_JUNK_CHARS) -> str:
    """Нормализовать текст карточки для поиска.

    Сжимает множественные пробелы, унифицирует переносы строк и табуляции,
    нормализует типографские кавычки и (опционально) удаляет мусорные
    символы. Регистр сохраняется: нормализация нужна для поиска по словарям,
    а не для изменения содержания.
    """
    if not text:
        return ""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\n", " ").replace("\t", " ")
    for source, target in QUOTE_NORMALIZATION.items():
        normalized = normalized.replace(source, target)
    if remove_junk_chars:
        normalized = _JUNK_RE.sub("", normalized)
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def detect_language(text: str) -> str:
    """Автоопределение языка (ru/en/mixed) по алфавиту текста.

    Эвристика по кириллице и латинице: если оба алфавита представлены
    заметной долёй (см. ``LANGUAGE_MIXED_MIN_SHARE``), текст считается
    смешанным; иначе побеждает алфавит-большинство. Текст без букв или на
    незнакомой письменности получает ``LANGUAGE_UNKNOWN``.
    """
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return LANGUAGE_UNKNOWN
    cyrillic = sum(1 for char in letters if _CYRILLIC_RE.match(char))
    latin = sum(1 for char in letters if _LATIN_RE.match(char))
    if not (cyrillic or latin):
        return LANGUAGE_UNKNOWN
    if not latin:
        return LANGUAGE_RU
    if not cyrillic:
        return LANGUAGE_EN
    latin_share = latin / (cyrillic + latin)
    if min(latin_share, 1.0 - latin_share) >= LANGUAGE_MIXED_MIN_SHARE:
        return LANGUAGE_MIXED
    return LANGUAGE_RU if cyrillic > latin else LANGUAGE_EN


def tokenize(text: str) -> list[str]:
    """Базовая whitespace-токенизация для rules/dicts (Этап 0)."""
    return text.split()


def generic_schema() -> CategorySchema:
    """Generic-схема: используется, когда категория карточки не определена."""
    return CategorySchema(category=GENERIC_CATEGORY, schema_version=GENERIC_SCHEMA_VERSION)


class SchemaRegistry:
    """Хранилище схем категорий с резолвом по ``category_id``/названию."""

    def __init__(self, schemas: Iterable[CategorySchema] | None = None) -> None:
        self._by_id: dict[str, CategorySchema] = {}
        self._by_name: dict[str, CategorySchema] = {}
        for schema in schemas or ():
            self.register(schema)

    def register(self, schema: CategorySchema) -> None:
        """Добавить схему в индексы по идентификатору и названию."""
        if schema.category_id:
            self._by_id[schema.category_id] = schema
        self._by_name[schema.category.strip().lower()] = schema

    def get(
        self, category_id: str | None = None, category_name: str | None = None
    ) -> CategorySchema | None:
        """Найти схему: сначала по идентификатору, затем по названию."""
        if category_id:
            schema = self._by_id.get(category_id)
            if schema is not None:
                return schema
        if category_name:
            return self._by_name.get(category_name.strip().lower())
        return None

    def resolve(self, card: ProductCard) -> CategorySchema:
        """Резолв схемы по карточке с fallback на generic-схему.

        category_id имеет приоритет над category_name; при отсутствии
        совпадений возвращается generic-схема, а category_id/category_name
        из входной карточки сохраняются в результате.
        """
        schema = self.get(card.category_id, card.category_name)
        return schema if schema is not None else generic_schema()


class PreprocessedCard(BaseModel):
    """Результат Этапа 0: нормализованный текст, язык, токены и схема."""

    card: ProductCard
    raw_text: str
    normalized_text: str
    language: str
    tokens: list[str]
    category_schema: CategorySchema


class CardPreprocessor:
    """Препроцессинг карточки перед каскадом экстракторов (Этап 0)."""

    def __init__(
        self,
        schemas: SchemaRegistry | None = None,
        *,
        remove_junk_chars: bool = DEFAULT_REMOVE_JUNK_CHARS,
    ) -> None:
        self._schemas = schemas if schemas is not None else SchemaRegistry()
        self._remove_junk_chars = remove_junk_chars

    def preprocess(self, card: ProductCard) -> PreprocessedCard:
        """Собрать ``raw_text``, нормализовать текст, определить язык и схему.

        ``raw_text`` берётся из контрактной модели (эквивалент формуле из
        спецификации); явно указанный в карточке язык имеет приоритет над
        автоопределением.
        """
        raw_text = card.raw_text
        normalized_text = normalize_text(raw_text, remove_junk_chars=self._remove_junk_chars)
        language = card.language.strip() if card.language else ""
        if not language:
            language = detect_language(normalized_text)
        return PreprocessedCard(
            card=card,
            raw_text=raw_text,
            normalized_text=normalized_text,
            language=language,
            tokens=tokenize(normalized_text),
            category_schema=self._schemas.resolve(card),
        )

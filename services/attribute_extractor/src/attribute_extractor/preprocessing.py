"""Препроцессинг карточки (Этап 0 пайплайна извлечения атрибутов).

Согласно openspec/specs/attribute_extractor.md (Этап 0): сбор ``raw_text``,
нормализация текста, автоопределение языка, базовая токенизация и резолв
``CategorySchema`` с fallback на generic-схему.
"""

import html
import json
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from attribute_extractor.constants import (
    CANONICAL_UNIT_ALIASES,
    CONTENT_VALUE_EXTRA_UNITS,
    CONTENT_VALUE_NUMBER_PATTERN,
    CYRILLIC_LETTER_PATTERN,
    DEFAULT_REMOVE_HTML_TAGS,
    DEFAULT_REMOVE_JUNK_CHARS,
    DEFAULT_REMOVE_SERVICE_NOISE,
    GENERIC_CATEGORY,
    GENERIC_SCHEMA_VERSION,
    HTML_TAG_PATTERN,
    JUNK_CHARS_PATTERN,
    LANGUAGE_EN,
    LANGUAGE_MIXED,
    LANGUAGE_MIXED_MIN_SHARE,
    LANGUAGE_RU,
    LANGUAGE_UNKNOWN,
    LATIN_LETTER_PATTERN,
    QUOTE_NORMALIZATION,
    SERVICE_NOISE_PATTERNS,
    WHITESPACE_PATTERN,
)
from attribute_extractor.errors import TextCleanupInvariantError
from specflow_contracts import CategorySchema, ProductCard

_JUNK_RE = re.compile(JUNK_CHARS_PATTERN)
_WHITESPACE_RE = re.compile(WHITESPACE_PATTERN)
_CYRILLIC_RE = re.compile(CYRILLIC_LETTER_PATTERN)
_LATIN_RE = re.compile(LATIN_LETTER_PATTERN)
_HTML_TAG_RE = re.compile(HTML_TAG_PATTERN, re.DOTALL)
_SERVICE_NOISE_RE = re.compile("|".join(SERVICE_NOISE_PATTERNS), re.IGNORECASE)
# Разделитель предложения; захватывается в split, чтобы при сборке вернуть его
# на место. Это сохраняет точку внутри числа (``6.7``) и сокращений (``т.д.``).
_SENTENCE_DELIMITER_RE = re.compile(r"([.;!?]+)")
_WORD_RE = re.compile(r"\w")


def _split_service_noise(text: str) -> tuple[str, list[str]]:
    """Разделить текст на очищенный вид и удалённые фрагменты шума.

    Общая механика для ``strip_service_noise`` и проверки инварианта очистки:
    возвращает очищенный текст и список удалённых фрагментов (целиком
    отброшенные вместе с пунктуацией предложения и вырезанные фразы-маркеры).
    """
    if not text:
        return text, []
    parts = _SENTENCE_DELIMITER_RE.split(text)
    kept: list[str] = []
    removed: list[str] = []
    for index in range(0, len(parts), 2):
        piece = parts[index]
        delimiter = parts[index + 1] if index + 1 < len(parts) else ""
        if not piece.strip():
            kept.append(delimiter)
            continue
        matches = list(_SERVICE_NOISE_RE.finditer(piece))
        cleaned = _SERVICE_NOISE_RE.sub(" ", piece)
        if matches and not _WORD_RE.search(cleaned):
            removed.append(piece + delimiter)
            continue
        removed.extend(match.group(0) for match in matches)
        kept.append(cleaned + delimiter)
    return _WHITESPACE_RE.sub(" ", "".join(kept)).strip(), removed


def strip_service_noise(text: str) -> str:
    """Удалить служебные вставки и водяные знаки из текста (Этап 0).

    Текст режется на предложения (разделители сохраняются). В каждом
    предложении удаляются фразы-маркеры из ``SERVICE_NOISE_PATTERNS`` (шум
    из EDA: «Подборки», «Продавец», BI-поля, «Гарантия предоставляется»,
    «Потратить бонусы», рекламные «шаблоны»). Если предложение состояло
    только из шума, оно отбрасывается целиком вместе с завершающей
    пунктуацией — иначе оставались бы висящие точки. Содержательные
    предложения лишь очищаются: их значения нужны для извлечения и
    grounding.

    Разделители сохраняются как в исходном тексте, поэтому десятичные точки
    (``6.7``) и сокращения (``т.д.``) не разрываются пробелами.
    """
    cleaned, _ = _split_service_noise(text)
    return cleaned


def normalize_text(
    text: str,
    *,
    remove_junk_chars: bool = DEFAULT_REMOVE_JUNK_CHARS,
    remove_html_tags: bool = DEFAULT_REMOVE_HTML_TAGS,
    remove_service_noise: bool = DEFAULT_REMOVE_SERVICE_NOISE,
) -> str:
    """Нормализовать текст карточки для поиска.

    Снимает HTML-теги (и декодирует HTML-сущности), сжимает множественные
    пробелы, унифицирует переносы строк и табуляции, нормализует
    типографские кавычки и (опционально) удаляет мусорные символы и
    служебные вставки/водяные знаки. Регистр сохраняется: нормализация
    нужна для поиска по словарям, а не для изменения содержания.

    Тег заменяется пробелом, а не удаляется целиком: ``<br>``/``<p>``
    разделяют слова, а склейка ``Экран<br>6.7`` → ``Экран6.7`` сломала бы
    сопоставление значений. Для инлайновых тегов (``<b>``, ``<sup>``)
    лишний пробел безвреден — токенизация и так работает по пробелам.
    """
    if not text:
        return ""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\n", " ").replace("\t", " ")
    if remove_html_tags:
        # Декодирование идёт до снятия тегов: экранированная разметка
        # (``&lt;b&gt;``) становится настоящим тегом и тоже удаляется.
        normalized = html.unescape(normalized)
        normalized = _HTML_TAG_RE.sub(" ", normalized)
    for source, target in QUOTE_NORMALIZATION.items():
        normalized = normalized.replace(source, target)
    if remove_junk_chars:
        normalized = _JUNK_RE.sub("", normalized)
    if remove_service_noise:
        normalized = strip_service_noise(normalized)
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def _build_content_value_re() -> re.Pattern[str]:
    """Собрать regex содержательных значений: число + известная единица.

    Единица распознаётся по словарю (ключи/значения ``CANONICAL_UNIT_ALIASES``
    и ``CONTENT_VALUE_EXTRA_UNITS``), а не по любому слову после числа:
    иначе «6.7 Подборки» склеивалось бы в одно значение со служебной
    вставкой и сравнение до/после очистки ломалось. Словари Этапа 6
    переиспользуются, чтобы проверка не расходилась с нормализацией единиц.
    """
    units = sorted(
        set(CANONICAL_UNIT_ALIASES)
        | set(CANONICAL_UNIT_ALIASES.values())
        | set(CONTENT_VALUE_EXTRA_UNITS),
        key=len,
        reverse=True,
    )
    unit_alternation = "|".join(re.escape(unit) for unit in units)
    return re.compile(
        rf"{CONTENT_VALUE_NUMBER_PATTERN}(?:\s+(?:{unit_alternation})(?!\w))?",
        re.IGNORECASE,
    )


_CONTENT_VALUE_RE = _build_content_value_re()


def extract_content_values(text: str) -> list[str]:
    """Извлечь содержательные значения (числа с единицами) из текста.

    Используется проверкой инварианта очистки: значения сравниваются между
    исходным и очищенным текстом как мультимножество (см.
    ``cleaning_invariant_violations``). Внутренние пробелы значения сжимаются
    до одного, чтобы сравнение не зависело от схлопывания пробелов.
    """
    return [
        _WHITESPACE_RE.sub(" ", match.group(0)).strip()
        for match in _CONTENT_VALUE_RE.finditer(text)
    ]


def cleaning_invariant_violations(
    raw_text: str,
    normalized_text: str,
    *,
    remove_junk_chars: bool = DEFAULT_REMOVE_JUNK_CHARS,
    remove_html_tags: bool = DEFAULT_REMOVE_HTML_TAGS,
    remove_service_noise: bool = DEFAULT_REMOVE_SERVICE_NOISE,
) -> list[str]:
    """Проверить, что очистка не изменила содержательные значения (Этап 0).

    Инвариант из openspec/specs/attribute_extractor.md (Этап 0): очистка
    улучшает вход для правил и NER, но не меняет числа и единицы.
    Сравниваются мультимножества значений (см. ``extract_content_values``):
    каждое значение очищенного текста должно присутствовать в исходном
    (ничего не добавлено/не искажено), а каждое значение исходного — в
    очищенном (ничего не потеряно).

    Служебный шум удаляется целиком по построению, поэтому значения из
    удалённых фрагментов (включая цифры в вырезанных служебных полях вроде
    «Продавец: … 777») исключаются из сравнения. HTML-разметка снимается до
    сравнения одинаково на обеих сторонах, поэтому цифры в тегах и сущностях
    не считаются содержательными значениями.

    Возвращает список текстовых описаний нарушений; пустой список —
    инвариант соблюдён.
    """
    if not raw_text:
        return []
    baseline = normalize_text(
        raw_text,
        remove_junk_chars=remove_junk_chars,
        remove_html_tags=remove_html_tags,
        remove_service_noise=False,
    )
    expected = Counter(extract_content_values(baseline))
    if remove_service_noise:
        _, removed_parts = _split_service_noise(baseline)
        for fragment in removed_parts:
            expected -= Counter(extract_content_values(fragment))
    actual = Counter(extract_content_values(normalized_text))
    violations = [
        f"значение появилось или изменилось при очистке: {value!r}"
        for value in sorted(actual - expected)
    ]
    violations.extend(
        f"значение потеряно при очистке: {value!r}" for value in sorted(expected - actual)
    )
    return violations


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
        self._schemas: list[CategorySchema] = []
        for schema in schemas or ():
            self.register(schema)

    @classmethod
    def from_file(cls, path: str | Path) -> "SchemaRegistry":
        """Загрузить реестр из JSON-артефакта ``build_category_schemas.py``.

        Формат: ``{"version": str, "schemas": [CategorySchema, ...]}``.
        Отсутствие файла → ``FileNotFoundError``, битый формат/валидация →
        исключение — вызывающий код (загрузка на старте сервиса) решает,
        деградировать ли до пустого реестра и generic-fallback.
        """
        with Path(path).open(encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict) or not isinstance(data.get("schemas"), list):
            raise ValueError(f"Некорректный формат реестра схем категорий: {path}")
        return cls(CategorySchema.model_validate(item) for item in data["schemas"])

    def register(self, schema: CategorySchema) -> None:
        """Добавить схему в индексы по идентификатору и названию."""
        if schema.category_id:
            self._by_id[schema.category_id] = schema
        self._by_name[schema.category.strip().lower()] = schema
        self._schemas.append(schema)

    def all(self) -> list[CategorySchema]:
        """Все зарегистрированные схемы в порядке регистрации (без generic)."""
        return list(self._schemas)

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
        remove_html_tags: bool = DEFAULT_REMOVE_HTML_TAGS,
        remove_service_noise: bool = DEFAULT_REMOVE_SERVICE_NOISE,
    ) -> None:
        self._schemas = schemas if schemas is not None else SchemaRegistry()
        self._remove_junk_chars = remove_junk_chars
        self._remove_html_tags = remove_html_tags
        self._remove_service_noise = remove_service_noise

    def preprocess(self, card: ProductCard) -> PreprocessedCard:
        """Собрать ``raw_text``, нормализовать текст, определить язык и схему.

        ``raw_text`` берётся из контрактной модели (эквивалент формуле из
        спецификации); явно указанный в карточке язык имеет приоритет над
        автоопределением. После нормализации проверяется инвариант очистки:
        очистка не меняет числа и единицы (``cleaning_invariant_violations``),
        иначе ``TextCleanupInvariantError`` — вход для правил/NER недоверен.
        """
        raw_text = card.raw_text
        normalized_text = normalize_text(
            raw_text,
            remove_junk_chars=self._remove_junk_chars,
            remove_html_tags=self._remove_html_tags,
            remove_service_noise=self._remove_service_noise,
        )
        violations = cleaning_invariant_violations(
            raw_text,
            normalized_text,
            remove_junk_chars=self._remove_junk_chars,
            remove_html_tags=self._remove_html_tags,
            remove_service_noise=self._remove_service_noise,
        )
        if violations:
            raise TextCleanupInvariantError(
                "Нарушен инвариант очистки (Этап 0): " + "; ".join(violations)
            )
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

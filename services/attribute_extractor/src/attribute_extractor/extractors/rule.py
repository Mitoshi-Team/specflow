"""Экстрактор на основе правил и шаблонов (Этап 3: ядро правил).

Согласно openspec/specs/attribute_extractor.md (Этап 3, §3.2), экстрактор
применяет регулярные выражения и близость ключевых слов к очищенному тексту
карточки (title/description) и возвращает код атрибута напрямую:
``extraction_method='rule'``, ``confidence=DEFAULT_DETERMINISTIC_CONFIDENCE``.
Целевые поля: ``brand``, ``model``, ``diagonal``, ``storage``, ``ram``,
``battery_capacity``, ``drive``, ``processor``, ``color``.

Поиск выполняется по ``normalize_text`` (Этап 0), спаны привязываются к
оригинальному тексту через ``locate_span``; значения чисел и единиц
форматируются общими функциями ``parse_number``/``format_number``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from attribute_extractor.constants import (
    CANONICAL_UNIT_ALIASES,
    COLOR_SYNONYMS,
    DEFAULT_DETERMINISTIC_CONFIDENCE,
    RULE_ADJACENT_MEMORY_TOKEN_GAP,
    RULE_BATTERY_PATTERN,
    RULE_COLOR_TEMPLATE_PATTERN,
    RULE_DIAGONAL_PATTERN,
    RULE_DRIVE_KEYWORDS,
    RULE_EXTRACTOR_NAME,
    RULE_EXTRACTOR_PRIORITY,
    RULE_KEYWORD_WINDOW,
    RULE_MEMORY_DEFAULT_CODE,
    RULE_MEMORY_PATTERN,
    RULE_MEMORY_SLASH_PATTERN,
    RULE_MODEL_KEYWORD_PATTERN,
    RULE_PROCESSOR_KEYWORD_PATTERN,
    RULE_PUNCTUATION_TRIM,
    RULE_RAM_KEYWORDS,
    RULE_RANGE_PREFIX_PATTERN,
    RULE_VALUE_BOUNDARY_PUNCT,
    RULE_VALUE_TOKEN_LIMIT,
    RULE_VALUE_TOKEN_PATTERN,
)
from attribute_extractor.extractors.base import BaseExtractor
from attribute_extractor.grounding import locate_span
from attribute_extractor.normalization import format_number, parse_number
from attribute_extractor.preprocessing import normalize_text
from attribute_extractor.references import BrandVocab
from specflow_contracts import (
    AttributeCandidate,
    CategorySchema,
    ExtractionMethod,
    ProductCard,
    Span,
    SpanField,
)

_DIAGONAL_RE = re.compile(RULE_DIAGONAL_PATTERN, re.IGNORECASE)
_MEMORY_RE = re.compile(RULE_MEMORY_PATTERN, re.IGNORECASE)
_MEMORY_SLASH_RE = re.compile(RULE_MEMORY_SLASH_PATTERN, re.IGNORECASE)
_BATTERY_RE = re.compile(RULE_BATTERY_PATTERN, re.IGNORECASE)
_COLOR_TEMPLATE_RE = re.compile(RULE_COLOR_TEMPLATE_PATTERN, re.IGNORECASE)
_MODEL_RE = re.compile(RULE_MODEL_KEYWORD_PATTERN, re.IGNORECASE)
_PROCESSOR_RE = re.compile(RULE_PROCESSOR_KEYWORD_PATTERN, re.IGNORECASE)
_VALUE_TOKEN_RE = re.compile(RULE_VALUE_TOKEN_PATTERN)
_RANGE_PREFIX_RE = re.compile(RULE_RANGE_PREFIX_PATTERN)
# Ключевые слова применяются к casefold-тексту с ё→е, поэтому — строчные.
_RAM_RES = tuple(re.compile(rf"(?<!\w){re.escape(word)}") for word in RULE_RAM_KEYWORDS)
_DRIVE_RES = tuple(re.compile(rf"(?<!\w){re.escape(word)}") for word in RULE_DRIVE_KEYWORDS)

_BATTERY_UNIT_FALLBACK = "мА·ч"
_DIAGONAL_UNIT_FALLBACK = "дюйм"


def _flexible_yo_pattern(word: str) -> str:
    """Собрать паттерн слова, где «е» может писаться как «ё» (зеленый/зелёный)."""
    return "".join("[ееё]" if char == "е" else re.escape(char) for char in word)


def _build_color_re() -> re.Pattern[str]:
    """Regex поиска цвета «как есть» в тексте: ключи и EN-синонимы словаря."""
    words = {word.casefold() for word in COLOR_SYNONYMS}
    for synonyms in COLOR_SYNONYMS.values():
        words.update(synonym.casefold() for synonym in synonyms)
    parts = [_flexible_yo_pattern(word) for word in sorted(words, key=len, reverse=True)]
    return re.compile(rf"(?<!\w)(?:{'|'.join(parts)})(?!\w)", re.IGNORECASE)


_COLOR_RE = _build_color_re()
_COLOR_BY_WORD: dict[str, str] = {}
for _canonical, _synonyms in COLOR_SYNONYMS.items():
    _COLOR_BY_WORD.setdefault(_canonical.casefold().replace("ё", "е"), _canonical)
    for _synonym in _synonyms:
        _COLOR_BY_WORD.setdefault(_synonym.casefold().replace("ё", "е"), _canonical)


def _build_brand_re(vocab: BrandVocab | None) -> re.Pattern[str] | None:
    """Regex бренда по словарю: границы слов, длинные варианты первыми.

    Без словаря бренд не извлекается (одиночное слово не является надёжным
    признаком бренда — «реклама», «оригинал» и т.п.).
    """
    if vocab is None:
        return None
    terms = {term.strip() for term in (*vocab.names, *vocab.aliases) if term and term.strip()}
    if not terms:
        return None
    ordered = sorted(terms, key=lambda term: (-len(term), term))
    alternation = "|".join(re.escape(term) for term in ordered)
    return re.compile(rf"(?<!\w)(?:{alternation})(?!\w)", re.IGNORECASE)


def _is_range_tail(text: str, start: int) -> bool:
    """Находится ли значение в хвосте диапазона («3000-5000 мАч»).

    Диапазоны продавцов не извлекаются как одиночные значения (см. обработку
    граничных случаев в attribute_extractor.md): значение было бы вырвано из
    контекста и неверно подтверждено текстом.
    """
    return bool(_RANGE_PREFIX_RE.search(text[:start]))


def _canonical_unit(unit: str, fallback: str) -> str:
    """Каноническая единица измерения по ``CANONICAL_UNIT_ALIASES``."""
    return CANONICAL_UNIT_ALIASES.get(unit.casefold(), fallback)


def _align_region_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    """Выровнять границы окна к ближайшему началу слова.

    Середина между значениями может разрезать слово («4 ГБ, SSD 1 ТБ»):
    без выравнивания окно левого значения не увидело бы «SSD», а окно правого
    начиналось бы с «dd». Разрезанное слово целиком уходит в правое окно —
    ключевое слово подписывает следующее за ним значение.
    """
    while 0 < start < len(text) and text[start].isalnum() and text[start - 1].isalnum():
        start -= 1
    while 0 < end < len(text) and text[end - 1].isalnum() and text[end].isalnum():
        end -= 1
    return start, end


def _keyword_classify(
    folded: str, region_start: int, region_end: int, value_start: int
) -> str | None:
    """Определить код поля памяти по ближайшему ключевому слову в окне.

    ``folded`` — casefold-текст с ё→е; окно ограничено соседними значениями
    памяти (чтобы «оператив» не «прилипал» к чужому числу) и
    ``RULE_KEYWORD_WINDOW`` вокруг значения; границы выравниваются по границе
    слова. Возвращает ``"ram"``/``"drive"`` или ``None``, если ключевых слов
    в окне нет.
    """
    region_start, region_end = _align_region_bounds(folded, region_start, region_end)
    segment = folded[region_start:region_end]
    best: tuple[int, str] | None = None
    for code, patterns in (("ram", _RAM_RES), ("drive", _DRIVE_RES)):
        for pattern in patterns:
            for match in pattern.finditer(segment):
                distance = abs(region_start + match.start() - value_start)
                if best is None or distance < best[0]:
                    best = (distance, code)
    return best[1] if best else None


def _adjacent(text: str, first_end: int, second_start: int) -> bool:
    """Соседние ли значения памяти: между ними не более N токенов."""
    return len(text[first_end:second_start].split()) <= RULE_ADJACENT_MEMORY_TOKEN_GAP


def _value_after_keyword(text: str, keyword_match: re.Match[str]) -> str | None:
    """Собрать последовательность латинско-цифровых токенов после ключевого слова.

    Стоп по кириллице и не-токенам; чистая пунктуация («:», «-») пропускается,
    чтобы разрыв «Модель - SM-S921B» не обрывал значение; токен с завершающей
    пунктуацией («Gen 2, 8 ядер») добавляется и завершает значение.
    """
    tokens: list[str] = []
    for raw_token in text[keyword_match.end() :].split():
        token = raw_token.strip(RULE_PUNCTUATION_TRIM)
        if not token:
            continue
        if not _VALUE_TOKEN_RE.fullmatch(token):
            break
        tokens.append(token)
        if len(tokens) >= RULE_VALUE_TOKEN_LIMIT:
            break
        if raw_token[-1] in RULE_VALUE_BOUNDARY_PUNCT:
            break
    value = " ".join(tokens)
    # Значение обязано содержать хотя бы одну латинскую букву: «Модель 2024»
    # и русские токены — не идентификатор модели/процессора.
    if not value or not re.search(r"[A-Za-z]", value):
        return None
    return value


def _keyword_value(text: str, keyword_re: re.Pattern[str]) -> str | None:
    """Значение модели/процессора: первое ключевое слово с распознанным значением."""
    for match in keyword_re.finditer(text):
        value = _value_after_keyword(text, match)
        if value is not None:
            return value
    return None


class RuleExtractor(BaseExtractor):
    """Регулярные выражения, шаблоны ключевых фраз и парсинг единиц (Этап 3)."""

    name = RULE_EXTRACTOR_NAME
    priority = RULE_EXTRACTOR_PRIORITY

    def __init__(self, brand_vocab: BrandVocab | None = None) -> None:
        self._brand_vocab = brand_vocab
        self._brand_re = _build_brand_re(brand_vocab)

    def extract(self, card: ProductCard, schema: CategorySchema) -> list[AttributeCandidate]:
        """Извлечь rule-кандидатов из title/description по детерминированным правилам."""
        candidates: list[AttributeCandidate] = []
        seen: set[tuple[str, str, SpanField]] = set()
        fields = (
            (SpanField.TITLE, card.title),
            (SpanField.DESCRIPTION, card.description),
        )
        for field, raw in fields:
            if not raw or not raw.strip():
                continue
            text = normalize_text(raw)
            if not text:
                continue
            for code, raw_value, normalized_value, evidence in self._extract_from_text(text):
                key = (code, normalized_value, field)
                if key in seen:
                    continue
                seen.add(key)
                span = locate_span(evidence, field, raw) or Span(field=field, text=evidence)
                candidates.append(
                    AttributeCandidate(
                        attribute_code=code,
                        raw_value=raw_value,
                        normalized_value=normalized_value,
                        confidence=DEFAULT_DETERMINISTIC_CONFIDENCE,
                        extraction_method=ExtractionMethod.RULE,
                        is_confirmed_in_text=True,
                        source_spans=[span],
                        evidence_text=evidence,
                    )
                )
        return candidates

    def _extract_from_text(self, text: str) -> Iterator[tuple[str, str, str, str]]:
        """Последовательность rule-правил по одному полю (детерминированный порядок)."""
        yield from self._diagonal_candidates(text)
        yield from self._battery_candidates(text)
        yield from self._memory_candidates(text)
        yield from self._color_candidates(text)
        model = _keyword_value(text, _MODEL_RE)
        if model is not None:
            yield ("model", model, model, model)
        processor = _keyword_value(text, _PROCESSOR_RE)
        if processor is not None:
            yield ("processor", processor, processor, processor)
        yield from self._brand_candidates(text)

    @staticmethod
    def _diagonal_candidates(text: str) -> Iterator[tuple[str, str, str, str]]:
        """Диагональ: число с единицей «дюйм»/inch/дюймовым символом (Этап 3)."""
        for match in _DIAGONAL_RE.finditer(text):
            if _is_range_tail(text, match.start()):
                continue
            number = match.group("number")
            unit = match.group("unit")
            normalized = (
                f"{format_number(parse_number(number))} "
                f"{_canonical_unit(unit, _DIAGONAL_UNIT_FALLBACK)}"
            )
            evidence = match.group(0)
            yield ("diagonal", evidence, normalized, evidence)

    @staticmethod
    def _battery_candidates(text: str) -> Iterator[tuple[str, str, str, str]]:
        """Ёмкость батареи: число с мА·ч/мАч/mAh (Этап 3)."""
        for match in _BATTERY_RE.finditer(text):
            if _is_range_tail(text, match.start()):
                continue
            number = match.group("number")
            normalized = (
                f"{format_number(parse_number(number))} "
                f"{_canonical_unit(match.group('unit'), _BATTERY_UNIT_FALLBACK)}"
            )
            evidence = match.group(0)
            yield ("battery_capacity", evidence, normalized, evidence)

    @staticmethod
    def _memory_candidates(text: str) -> Iterator[tuple[str, str, str, str]]:
        """Память: слэш-пары (ОЗУ/накопитель), соседние и одиночные значения.

        Дисамбигуация: «8/256 ГБ» → первый объём — ОЗУ, второй — по ключевому
        слову (иначе встроенный накопитель); одиночное значение без ключевых
        слов считается встроенным накопителем (``RULE_MEMORY_DEFAULT_CODE``).
        """
        folded = text.lower().replace("ё", "е")
        slash_matches = list(_MEMORY_SLASH_RE.finditer(text))
        slash_spans = [(match.start(), match.end()) for match in slash_matches]
        for match in slash_matches:
            unit = _canonical_unit(match.group("unit"), "ГБ")
            evidence = match.group(0)
            second_start = match.start("second")
            yield (
                "ram",
                evidence,
                f"{format_number(parse_number(match.group('first')))} {unit}",
                evidence,
            )
            region_start = (match.start() + second_start) // 2
            region_end = min(len(text), match.end() + RULE_KEYWORD_WINDOW)
            code = _keyword_classify(folded, region_start, region_end, second_start)
            yield (
                code or RULE_MEMORY_DEFAULT_CODE,
                evidence,
                f"{format_number(parse_number(match.group('second')))} {unit}",
                evidence,
            )
        singles = [
            match
            for match in _MEMORY_RE.finditer(text)
            if not _is_range_tail(text, match.start())
            and not any(start < match.end() and match.start() < end for start, end in slash_spans)
        ]
        count = len(singles)
        for index, match in enumerate(singles):
            left = 0 if index == 0 else (singles[index - 1].end() + match.start()) // 2
            right = (
                len(text) if index + 1 == count else (match.end() + singles[index + 1].start()) // 2
            )
            left = max(left, match.start() - RULE_KEYWORD_WINDOW)
            right = min(right, match.end() + RULE_KEYWORD_WINDOW)
            code = _keyword_classify(folded, left, right, match.start())
            if (
                code is None
                and index + 1 < count
                and _adjacent(text, match.end(), singles[index + 1].start())
            ):
                # Первое из двух близких значений без ключевых слов — ОЗУ:
                # типичная пара «ОЗУ + встроенный накопитель» без уточнений.
                code = "ram"
            if code is None:
                code = RULE_MEMORY_DEFAULT_CODE
            unit = _canonical_unit(match.group("unit"), "ГБ")
            evidence = match.group(0)
            yield (
                code,
                evidence,
                f"{format_number(parse_number(match.group('number')))} {unit}",
                evidence,
            )

    @staticmethod
    def _color_candidates(text: str) -> Iterator[tuple[str, str, str, str]]:
        """Цвет: шаблон «Цвет: чёрный» и одиночное слово из словаря цветов."""
        for match in _COLOR_TEMPLATE_RE.finditer(text):
            value = match.group("value").casefold().replace("ё", "е")
            # Ключи словаря — канонические значения, значения — EN-синонимы.
            canonical = value if value in COLOR_SYNONYMS else None
            if canonical is None:
                continue  # значение вне словаря («лавандовый») — не угадываем
            evidence = match.group("value")
            yield ("color", evidence, canonical, evidence)
        for match in _COLOR_RE.finditer(text):
            canonical = _COLOR_BY_WORD.get(match.group(0).casefold().replace("ё", "е"))
            if canonical is None:
                continue
            evidence = match.group(0)
            yield ("color", evidence, canonical, evidence)

    def _brand_candidates(self, text: str) -> Iterator[tuple[str, str, str, str]]:
        """Бренд: границы слов по словарю брендов (без словаря не извлекается)."""
        if self._brand_re is None or self._brand_vocab is None:
            return
        for match in self._brand_re.finditer(text):
            canonical = self._brand_vocab.resolve(match.group(0))
            if canonical is None:
                continue  # стоп-слово словаря
            evidence = match.group(0)
            yield ("brand", evidence, canonical, evidence)

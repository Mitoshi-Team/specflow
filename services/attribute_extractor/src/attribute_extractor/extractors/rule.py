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
from collections.abc import Collection, Iterator

from attribute_extractor.constants import (
    CANONICAL_UNIT_ALIASES,
    COLOR_SYNONYMS,
    DEFAULT_DETERMINISTIC_CONFIDENCE,
    RULE_ADJACENT_MEMORY_TOKEN_GAP,
    RULE_BATTERY_KEYWORDS,
    RULE_BATTERY_PATTERN,
    RULE_CODE_TOKEN_MIN_LENGTH,
    RULE_COLOR_TEMPLATE_PATTERN,
    RULE_DIAGONAL_KEYWORDS,
    RULE_DIAGONAL_PATTERN,
    RULE_DRIVE_KEYWORDS,
    RULE_EXTRACTOR_NAME,
    RULE_EXTRACTOR_PRIORITY,
    RULE_KEY_PHRASE_TOKEN_GAP,
    RULE_KEYWORD_WINDOW,
    RULE_LAPTOP_CATEGORY_MARKER,
    RULE_MEMORY_DEFAULT_CODE,
    RULE_MEMORY_EXCLUSION_MARKERS,
    RULE_MEMORY_PATTERN,
    RULE_MEMORY_SLASH_PATTERN,
    RULE_MODEL_KEYWORD_PATTERN,
    RULE_MODEL_NUMBER_DIGITS,
    RULE_MODEL_STOPWORDS,
    RULE_PROCESSOR_ANCHORS,
    RULE_PROCESSOR_CASE_FIXES,
    RULE_PROCESSOR_KEYWORD_PATTERN,
    RULE_PROCESSOR_TOKEN_LIMIT,
    RULE_PROCESSOR_VENDORS,
    RULE_PROXIMITY_BLOCKED_TAIL_PATTERN,
    RULE_PROXIMITY_DEFAULT_UNITS,
    RULE_PROXIMITY_NUMBER_PATTERN,
    RULE_PROXIMITY_VALUE_RANGES,
    RULE_PUNCTUATION_TRIM,
    RULE_RAM_KEYWORDS,
    RULE_RAM_MAX_GB,
    RULE_RANGE_PREFIX_PATTERN,
    RULE_RANGE_SUFFIX_PATTERN,
    RULE_STORAGE_KEYWORDS,
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
_RANGE_SUFFIX_RE = re.compile(RULE_RANGE_SUFFIX_PATTERN)
_PROXIMITY_NUMBER_RE = re.compile(RULE_PROXIMITY_NUMBER_PATTERN)
_TOKEN_RE = re.compile(r"\S+")
# Хвост значения: разделители, затем чужая мера («80 см», «60 Гц») или цифра
# соотношения («16:9») — такие числа полю не являются.
_BLOCKED_TAIL_RE = re.compile(
    rf"[\s{re.escape(RULE_PUNCTUATION_TRIM)}]*(?<!\w)(?:{RULE_PROXIMITY_BLOCKED_TAIL_PATTERN})(?!\w)",
    re.IGNORECASE,
)
_DIGIT_TAIL_RE = re.compile(rf"[\s{re.escape(RULE_PUNCTUATION_TRIM)}]*\d")
# Одиночная мера/единица («Hz», «GB», «inch») из того же списка, что и хвосты
# чужих мер у чисел: такой токен — характеристика, а не часть названия модели.
_MODEL_MEASURE_RE = re.compile(
    rf"(?<!\w)(?:{RULE_PROXIMITY_BLOCKED_TAIL_PATTERN})(?!\w)", re.IGNORECASE
)


def _keyword_res(words: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    """Regex ключевых слов с префиксным совпадением («оператив» → «оперативный»).

    Ключевые слова применяются к casefold-тексту с ё→е, поэтому — строчные.
    """
    return tuple(re.compile(rf"(?<!\w){re.escape(word)}") for word in words)


# Ключевые слова применяются к casefold-тексту с ё→е, поэтому — строчные.
_RAM_RES = _keyword_res(RULE_RAM_KEYWORDS)
_DRIVE_RES = _keyword_res(RULE_DRIVE_KEYWORDS)
_DIAGONAL_RES = _keyword_res(RULE_DIAGONAL_KEYWORDS)
_BATTERY_RES = _keyword_res(RULE_BATTERY_KEYWORDS)
_STORAGE_RES = _keyword_res(RULE_STORAGE_KEYWORDS)
_MEMORY_EXCLUSION_RES = _keyword_res(RULE_MEMORY_EXCLUSION_MARKERS)
# Якорь семейства/вендора процессора в тексте: слово с границами
# («/Core i5» — матч; «8-core» — тоже якорь, но итог без цифр отбраковывается).
_PROCESSOR_ANCHOR_TEXT_RE = re.compile(
    rf"(?<!\w)(?:{'|'.join(RULE_PROCESSOR_ANCHORS)})\b",
    re.IGNORECASE,
)
# Вендор включается в значение только перед якорями, где это соответствует
# gold-канону («Intel Core i5», «Intel Celeron», «AMD Ryzen»); «Snapdragon
# 680» каноничен без вендора.
_PROCESSOR_VENDOR_PREFIXES = frozenset({"core", "ryzen", "celeron"})
# Дефис в номере процессора — разделитель («8400-Ultra» → «8400 Ultra»).
_PROCESSOR_DASH_FIX_RE = re.compile(r"(?<=\d)-(?=[A-Za-z])")
_PROCESSOR_ANCHOR_RES = _keyword_res(RULE_PROCESSOR_ANCHORS)
_PROCESSOR_VENDOR_RES = _keyword_res(RULE_PROCESSOR_VENDORS)
# Порядок групп задаёт приоритет ключевых слов одного значения: конкретные
# ключи ОЗУ/накопителя важнее общих («оперативная память» → ram, а не storage).
_KEY_PHRASE_GROUPS = (
    ("ram", _RAM_RES),
    ("drive", _DRIVE_RES),
    ("diagonal", _DIAGONAL_RES),
    ("battery_capacity", _BATTERY_RES),
    ("storage", _STORAGE_RES),
)
_MEMORY_KEYWORD_GROUPS = (("ram", _RAM_RES), ("drive", _DRIVE_RES))

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


def _nearest_keyword_code(
    folded: str,
    region_start: int,
    region_end: int,
    value_start: int,
    groups: tuple[tuple[str, tuple[re.Pattern[str], ...]], ...],
) -> str | None:
    """Определить код поля по ближайшему ключевому слову в окне.

    ``folded`` — casefold-текст с ё→е; окно ограничено соседними значениями
    и ``RULE_KEYWORD_WINDOW`` вокруг значения, границы выравниваются по границе
    слова. Возвращает код ближайшей группы или ``None``, если ключевых слов
    в окне нет.
    """
    region_start, region_end = _align_region_bounds(folded, region_start, region_end)
    segment = folded[region_start:region_end]
    best: tuple[int, str] | None = None
    for code, patterns in groups:
        for pattern in patterns:
            for match in pattern.finditer(segment):
                distance = abs(region_start + match.start() - value_start)
                if best is None or distance < best[0]:
                    best = (distance, code)
    return best[1] if best else None


def _keyword_classify(
    folded: str, region_start: int, region_end: int, value_start: int
) -> str | None:
    """Определить код поля памяти по ближайшему ключевому слову в окне.

    Возвращает ``"ram"``/``"drive"`` или ``None``, если ключевых слов
    в окне нет (значение памяти без ключевых слов разбирают вызывающие
    правила: встроенный накопитель или эвристика соседства).
    """
    return _nearest_keyword_code(
        folded, region_start, region_end, value_start, _MEMORY_KEYWORD_GROUPS
    )


def _adjacent(text: str, first_end: int, second_start: int) -> bool:
    """Соседние ли значения памяти: между ними не более N токенов."""
    return len(text[first_end:second_start].split()) <= RULE_ADJACENT_MEMORY_TOKEN_GAP


def _is_excluded_memory(text: str, start: int, end: int) -> bool:
    """Чужой ли это объём: рядом маркер исключения (кэш, видеопамять, расширение).

    Окно в ``RULE_KEYWORD_WINDOW`` символов в обе стороны; маркеры применяются
    к casefold-тексту с ё→е («кэш» ловит «cache»-подобные русские написания).
    """
    left = max(0, start - RULE_KEYWORD_WINDOW)
    right = min(len(text), end + RULE_KEYWORD_WINDOW)
    window = text[left:right].lower().replace("ё", "е")
    return any(pattern.search(window) for pattern in _MEMORY_EXCLUSION_RES)


def _leading_value_token(raw_token: str) -> str:
    """Ведущий латинско-цифровой префикс токена («Pro/16"/Core» → «Pro»).

    Токены со слэшами/кавычками внутри («Katana 17/17.3"/...») не проходят
    ``_VALUE_TOKEN_RE`` целиком, но их префикс — часть значения («Katana 17»,
    «Ryzen 7 260»); остаток токена — чужая характеристика.
    """
    match = _VALUE_TOKEN_RE.match(raw_token)
    return match.group(0) if match else ""


def _value_after_keyword(
    text: str, keyword_match: re.Match[str], *, require_digit: bool = False
) -> str | None:
    """Собрать последовательность латинско-цифровых токенов после ключевого слова.

    Стоп по кириллице и не-токенам; чистая пунктуация («:», «-») пропускается,
    чтобы разрыв «Модель - SM-S921B» не обрывал значение; токен с завершающей
    пунктуацией («Gen 2, 8 ядер») добавляется и завершает значение. Открывающая
    скобка обрывает сбор до среза пунктуации: «Intel 125H (14 ядер)» — значение
    «Intel 125H», а не «Intel 125H 14». Для процессора
    (``require_digit=True``) одиночный токен без цифр («Unisoc с четырьмя
    ядрами») не является идентифицируемым значением.
    """
    tokens: list[str] = []
    for raw_token in text[keyword_match.end() :].split():
        if raw_token.startswith("("):
            break
        token = raw_token.strip(RULE_PUNCTUATION_TRIM)
        if not token:
            continue
        if not _VALUE_TOKEN_RE.fullmatch(token):
            token = _leading_value_token(raw_token)
            if not token:
                break
            tokens.append(token)
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
    if require_digit and not any(char.isdigit() for char in value):
        return None
    for source, replacement in RULE_PROCESSOR_CASE_FIXES:
        value = value.replace(source, replacement)
    return value


def _keyword_value(
    text: str, keyword_re: re.Pattern[str], *, require_digit: bool = False
) -> str | None:
    """Значение модели/процессора: первое ключевое слово с распознанным значением."""
    for match in keyword_re.finditer(text):
        value = _value_after_keyword(text, match, require_digit=require_digit)
        if value is not None:
            return value
    return None


def _build_model_stop_words() -> frozenset[str]:
    """Стоп-слова модели после бренда: единицы, ключевые слова полей, цвета.

    Словарь собирается из уже существующих констант правил, чтобы список
    стоп-слов не расходился с ними («512GB», «IPS», «Black» — характеристика,
    а не продолжение названия модели). Якоря процессоров («Core», «Ryzen»)
    тоже характеристики — после них продолжается спецификация, не модель.
    """
    words = {word.casefold() for word in CANONICAL_UNIT_ALIASES}
    words.update(canonical.casefold() for canonical in CANONICAL_UNIT_ALIASES.values())
    for keywords in (
        RULE_RAM_KEYWORDS,
        RULE_DRIVE_KEYWORDS,
        RULE_DIAGONAL_KEYWORDS,
        RULE_BATTERY_KEYWORDS,
        RULE_STORAGE_KEYWORDS,
        RULE_PROCESSOR_ANCHORS,
        RULE_PROCESSOR_VENDORS,
    ):
        words.update(keyword.casefold() for keyword in keywords)
    for canonical, synonyms in COLOR_SYNONYMS.items():
        words.add(canonical.casefold())
        words.update(synonym.casefold() for synonym in synonyms)
    words.update(RULE_MODEL_STOPWORDS)
    return frozenset(words)


_MODEL_STOP_WORDS = _build_model_stop_words()


_MEMORY_SUBSTR_RE = re.compile(r"\d\s*(?:gb|гб|tb|тб|mb|мб)$", re.IGNORECASE)


def _is_model_stop_token(token: str) -> bool:
    """Токен — единица/характеристика/цвет, а не часть названия модели.

    Ведущие цифры снимаются: «512GB» → «gb», «165Hz» → «hz» — ёмкость или
    частота в заголовке пишутся слитно с числом; «8+256GB» — пара памяти,
    склеенная с объёмом («+256GB» в хвосте).
    """
    bare = token.casefold().lstrip("0123456789")
    if not bare:
        return False  # чистое число разбирается отдельным правилом
    if _MEMORY_SUBSTR_RE.search(bare):
        return True
    return bare in _MODEL_STOP_WORDS or bool(_MODEL_MEASURE_RE.fullmatch(bare))


def _is_model_token(token: str) -> bool:
    """Похож ли токен на продолжение названия модели (латиница и не характеристика)."""
    if not token or not _VALUE_TOKEN_RE.fullmatch(token):
        return False
    return not _is_model_stop_token(token)


def _following_token(tokens: list[str], index: int) -> str:
    """Ближайший следующий значимый токен (без разделителей-пустышек)."""
    for raw_token in tokens[index + 1 :]:
        token = raw_token.strip(RULE_PUNCTUATION_TRIM)
        if token:
            return token
    return ""


def _is_code_token(token: str) -> bool:
    """Токен — «код конфигурации» (длинная цифро-буквенная смесь, ≥8 символов).

    «UX3405MA-QD919», «82VG00MQUE» — SKU-коды после названия модели, а не её
    продолжение («IdeaPad 1 15AMN7» — короткий код серии, входящий в модель).
    """
    return (
        len(token) >= RULE_CODE_TOKEN_MIN_LENGTH
        and any(char.isdigit() for char in token)
        and any(char.isalpha() for char in token)
    )


def _model_value_after_brand(text: str, brand_match: re.Match[str]) -> str | None:
    """Модель после бренда: латинско-цифровые токены до характеристики.

    «Apple iPhone 13 Pro 256 ГБ» → «iPhone 13 Pro». Тот же сбор токенов, что
    у ``_value_after_keyword`` (стоп по кириллице, лимит токенов, обязателна
    латинская буква), плюс обрывы на характеристиках:

    - токен-единица/технология/цвет («512GB», «IPS», «Black»);
    - «голое» число ≥ ``RULE_MODEL_NUMBER_DIGITS`` цифр, за которым не следует
      токен модели («128 ГБ» — ёмкость, но «250 G9» — номер модели);
    - «голое» число после токена с цифрами («OLED55C4 55 4K» — это размер);
    - код конфигурации (``_is_code_token`` — «UX3405MA-QD919», «82VG00MQUE»).
    """
    tokens = text[brand_match.end() :].split()
    collected: list[str] = []
    previous_has_digit = False
    for index, raw_token in enumerate(tokens):
        token = raw_token.strip(RULE_PUNCTUATION_TRIM)
        if not token:
            continue
        if not _VALUE_TOKEN_RE.fullmatch(token):
            # Токен со слэшами/кавычками («Katana 17/17.3"/Core»): ведущий
            # префикс — часть модели, остаток — чужая характеристика.
            # Цифровой префикс добавляется, только если хвост не является
            # памятью/диагональю/парой («Galaxy S26 Ultra 1 Tb», «MatePad SE
            # 11#», «8+256»): иначе цифра — чужой объём.
            leading = _leading_value_token(raw_token)
            if leading and _is_model_token(leading) and not leading.isdigit():
                if not re.fullmatch(r"[iI][3579]", leading):
                    collected.append(leading)
            elif leading and leading.isdigit():
                tail = raw_token.lstrip()[raw_token.lstrip().find(leading) + len(leading) :]
                tail = tail.lstrip()
                if not re.match(
                    rf"(?:[.,]\d|[+/]\d|\s*(?:{'|'.join(CANONICAL_UNIT_ALIASES)}))",
                    tail,
                    re.IGNORECASE,
                ):
                    collected.append(leading)
            break
        if _is_code_token(token) and collected:
            # Код конфигурации после названия модели («Zenbook 14 UX3405MA»)
            # обрывает сбор; сам по себе код — легальная модель («WH-1000XM5»).
            break
        if _is_model_stop_token(token):
            break
        if token.isdigit() and (
            previous_has_digit
            or (
                len(token) >= RULE_MODEL_NUMBER_DIGITS
                and not _is_model_token(_following_token(tokens, index))
            )
        ):
            break
        collected.append(token)
        previous_has_digit = any(char.isdigit() for char in token)
        if len(collected) >= RULE_VALUE_TOKEN_LIMIT:
            break
        if raw_token[-1] in RULE_VALUE_BOUNDARY_PUNCT:
            break
    value = " ".join(collected)
    if not value or not re.search(r"[A-Za-z]", value):
        return None
    return value


def _processor_anchor_values(text: str) -> Iterator[str]:
    """Процессор без ключевого слова: якорь семейства + до 3 токенов значения.

    Заголовки перечисляют процессор слэшами («.../Core i5-12450H/8/512GB»,
    «Ryzen 7 260/16Гб», «Snapdragon 680») без слова «процессор». Вендор
    включается в значение только перед якорями «Core»/«Ryzen» (gold-канон:
    «Intel Core i5», «AMD Ryzen», но «Snapdragon 680» без «Qualcomm»); номер
    модели процессора может быть «кодом» («9955HX3D», «i7-13620H») и не
    обрывается правилом кодов моделей. Пересекающиеся якоря («Intel Core
    i5»): побеждает первый, якоря внутри собранного диапазона пропускаются.
    Итог обязан содержать цифру: семейство без номера («core») — не модель.
    """
    collected_spans: list[tuple[int, int]] = []
    for anchor_match in _PROCESSOR_ANCHOR_TEXT_RE.finditer(text):
        start, end = anchor_match.span()
        if any(
            covered_start < end and start < covered_end
            for covered_start, covered_end in collected_spans
        ):
            continue
        collected: list[str] = [anchor_match.group(0)]
        if anchor_match.group(0).casefold() in _PROCESSOR_VENDOR_PREFIXES and start > 0:
            previous = text[:start].split()
            vendor = previous[-1].strip(RULE_PUNCTUATION_TRIM) if previous else ""
            if vendor and any(
                pattern.fullmatch(vendor.casefold().replace("ё", "е"))
                for pattern in _PROCESSOR_VENDOR_RES
            ):
                collected.insert(0, vendor)
        consumed_end = end
        for raw_next in text[end:].split():
            next_token = raw_next.strip(RULE_PUNCTUATION_TRIM)
            if not next_token or raw_next.startswith("("):
                break
            if not _VALUE_TOKEN_RE.fullmatch(next_token):
                leading = _leading_value_token(raw_next)
                if not leading or _is_model_stop_token(leading):
                    break
                collected.append(leading)
                consumed_end = end + 1 + text[end:].find(raw_next) + len(raw_next)
                break
            if _is_model_stop_token(next_token):
                break
            collected.append(next_token)
            consumed_end = end + 1 + text[end:].find(raw_next) + len(raw_next)
            if (
                raw_next[-1] in RULE_VALUE_BOUNDARY_PUNCT
                or len(collected) >= RULE_PROCESSOR_TOKEN_LIMIT
            ):
                break
        collected_spans.append((start, consumed_end))
        value = " ".join(collected)
        if not any(char.isdigit() for char in value):
            continue
        value = _PROCESSOR_DASH_FIX_RE.sub(" ", value)
        for source, replacement in RULE_PROCESSOR_CASE_FIXES:
            value = value.replace(source, replacement)
        yield value


def _covered_spans(text: str) -> list[tuple[int, int]]:
    """Отрезки, уже разобранные правилами единиц: их поле назначено и не меняется."""
    spans: list[tuple[int, int]] = []
    for pattern in (_DIAGONAL_RE, _BATTERY_RE, _MEMORY_SLASH_RE, _MEMORY_RE):
        spans.extend(match.span() for match in pattern.finditer(text))
    return spans


def _is_covered(span: tuple[int, int], covered: list[tuple[int, int]]) -> bool:
    """Пересекается ли число с уже разобранным правилами единиц отрезком."""
    start, end = span
    return any(
        covered_start < end and start < covered_end for covered_start, covered_end in covered
    )


def _first_number_after(text: str, start: int) -> tuple[int, int] | None:
    """Первое число в ближайшем токене после ключевого слова.

    Токены без цифр — уточнения («Диагональ экрана 6,7»); поиск останавливается
    на первом токене с цифрой, чтобы ключевое слово не «перепрыгивало» соседние
    значения («Оперативная память 8 ГБ, Память 256») и не привязывало бы их
    к себе. Токен с цифрами без безусловного числа («SM-S921B», «9H») тоже
    завершает поиск: слитое с буквами число не является извлекаемым значением.
    """
    gap = 0
    for token in _TOKEN_RE.finditer(text, start):
        if not any(char.isdigit() for char in token.group()):
            gap += 1
            if gap > RULE_KEY_PHRASE_TOKEN_GAP:
                return None
            continue
        number = _PROXIMITY_NUMBER_RE.search(text, token.start(), token.end())
        return number.span() if number is not None else None
    return None


def _is_range_part(text: str, start: int, end: int) -> bool:
    """Находится ли число внутри диапазона («3000-5000»): граница не извлекается."""
    return bool(_is_range_tail(text, start) or _RANGE_SUFFIX_RE.match(text, end))


def _has_blocked_tail(text: str, end: int) -> bool:
    """Стоит ли после числа чужая мера («80 см») или цифра соотношения («16:9»).

    Контекст ключевой фразы определяет поле, но не отменяет единицу измерения:
    «Диагональ 80 см» — не 80 дюймов.
    """
    rest = text[end:]
    if _DIGIT_TAIL_RE.match(rest):
        return True
    return bool(_BLOCKED_TAIL_RE.match(rest))


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
        category = (card.category_name or "").casefold()
        default_memory_code = (
            "drive" if RULE_LAPTOP_CATEGORY_MARKER in category else RULE_MEMORY_DEFAULT_CODE
        )
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
            for code, raw_value, normalized_value, evidence in self._extract_from_text(
                text, default_memory_code=default_memory_code
            ):
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

    def extract_for_missing(
        self, card: ProductCard, schema: CategorySchema, missing: Collection[str]
    ) -> list[AttributeCandidate]:
        """Rules-fallback (Этап 7): правила только для незакрытых полей схемы.

        ``missing`` — коды обязательных атрибутов, которые не закрыли
        предыдущие пути каскада (NER-путь; seller-атрибуты пайплайном не
        используются — Этап 2 удалён). Возвращаются только кандидаты с кодом
        из ``missing``: полными правилами обязательные поля не дублируются,
        а необязательные fallback не заполняет. Пустой ``missing`` — пустой
        список (правила не выполняются вхолостую).

        Контракт этапа 7 (openspec/specs/attribute_extractor.md): кандидатам
        fallback закрепляются ``extraction_method='rule'`` и
        ``confidence=DEFAULT_DETERMINISTIC_CONFIDENCE`` — метаданные
        гарантируются на границе fallback, а не наследуются от способа
        поиска значения внутри правил.
        """
        if not missing:
            return []
        return [
            candidate.model_copy(
                update={
                    "extraction_method": ExtractionMethod.RULE,
                    "confidence": DEFAULT_DETERMINISTIC_CONFIDENCE,
                }
            )
            for candidate in self.extract(card, schema)
            if candidate.attribute_code in missing
        ]

    def _extract_from_text(
        self, text: str, *, default_memory_code: str = RULE_MEMORY_DEFAULT_CODE
    ) -> Iterator[tuple[str, str, str, str]]:
        """Последовательность rule-правил по одному полю (детерминированный порядок)."""
        yield from self._diagonal_candidates(text)
        yield from self._battery_candidates(text)
        yield from self._memory_candidates(text, default_memory_code)
        yield from self._proximity_candidates(text)
        yield from self._color_candidates(text)
        # Модель после бренда приоритетнее ключа «Модель:»: gold-канон строится
        # по заголовку, а ключ в описании часто описывает вариант исполнения
        # («Модель: Note 12 Pro+» при заголовке «Redmi Note 12 Pro+»). Два
        # разных значения одного кода создали бы ложный конфликт в мёрдже.
        model_given = False
        for brand_model in self._brand_model_values(text):
            model_given = True
            yield ("model", brand_model, brand_model, brand_model)
        if not model_given:
            model = _keyword_value(text, _MODEL_RE)
            if model is not None:
                yield ("model", model, model, model)
        # Процессор: якорь семейства в тексте приоритетнее ключевого слова —
        # заголовки перечисляют процессор слэшами без слова «процессор».
        processor_given = False
        for anchor_value in _processor_anchor_values(text):
            processor_given = True
            yield ("processor", anchor_value, anchor_value, anchor_value)
        if not processor_given:
            processor = _keyword_value(text, _PROCESSOR_RE, require_digit=True)
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
    def _memory_candidates(
        text: str, default_memory_code: str = RULE_MEMORY_DEFAULT_CODE
    ) -> Iterator[tuple[str, str, str, str]]:
        """Память: слэш-пары (ОЗУ/накопитель), соседние и одиночные значения.

        Дисамбигуация: «8/256 ГБ» → первый объём — ОЗУ (всегда в гигабайтах:
        «32/1TB» — это 32 ГБ ОЗУ), второй — по ключевому слову, иначе код по
        ``default_memory_code`` (ноутбуки — drive, остальное — storage);
        одиночное значение без ключевых слов считается встроенным накопителем.
        Значения рядом с маркерами-исключениями (кэш, видеопамять, карты
        памяти/расширение) — чужие объёмы и не извлекаются.
        """
        folded = text.lower().replace("ё", "е")
        slash_matches = [
            match
            for match in _MEMORY_SLASH_RE.finditer(text)
            # «Ryzen 7 260/16Гб» — 260 не является объёмом ОЗУ: пара из таких
            # токенов не собирается, значения остаются одиночному правилу.
            if parse_number(match.group("first")) <= RULE_RAM_MAX_GB
        ]
        slash_spans = [(match.start(), match.end()) for match in slash_matches]
        for match in slash_matches:
            evidence = match.group(0)
            second_start = match.start("second")
            yield (
                "ram",
                evidence,
                f"{format_number(parse_number(match.group('first')))} ГБ",
                evidence,
            )
            region_start = (match.start() + second_start) // 2
            region_end = min(len(text), match.end() + RULE_KEYWORD_WINDOW)
            code = _keyword_classify(folded, region_start, region_end, second_start)
            unit = _canonical_unit(match.group("unit") or "ГБ", "ГБ")
            yield (
                code or default_memory_code,
                evidence,
                f"{format_number(parse_number(match.group('second')))} {unit}",
                evidence,
            )
        singles = [
            match
            for match in _MEMORY_RE.finditer(text)
            if not _is_range_tail(text, match.start())
            and not any(start < match.end() and match.start() < end for start, end in slash_spans)
            and not _is_excluded_memory(text, match.start(), match.end())
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
                code = default_memory_code
            unit = _canonical_unit(match.group("unit"), "ГБ")
            evidence = match.group(0)
            yield (
                code,
                evidence,
                f"{format_number(parse_number(match.group('number')))} {unit}",
                evidence,
            )

    @staticmethod
    def _proximity_candidates(text: str) -> Iterator[tuple[str, str, str, str]]:
        """Шаблон ключевой фразы и близость ключевого слова к значению (Этап 3).

        Ключевое слово поля связывается со значением без единицы, стоящим не
        дальше ``RULE_KEY_PHRASE_TOKEN_GAP`` токенов («Диагональ: 6,7»,
        «Ёмкость аккумулятора 4500», «ОЗУ: 8»); единица берётся из
        ``RULE_PROXIMITY_DEFAULT_UNITS``. Отсечки: числа, разобранные правилами
        единиц; границы диапазонов; чужая мера после числа («80 см») и значения
        вне ``RULE_PROXIMITY_VALUE_RANGES`` — контекст определяет поле, но не
        позволяет выдумать физически невозможное значение.
        """
        folded = text.lower().replace("ё", "е")
        covered = _covered_spans(text)
        bindings: dict[tuple[int, int], tuple[int, str]] = {}
        for priority, (code, patterns) in enumerate(_KEY_PHRASE_GROUPS):
            for pattern in patterns:
                for match in pattern.finditer(folded):
                    span = _first_number_after(text, match.end())
                    if span is None or _is_covered(span, covered):
                        continue
                    if _is_range_part(text, *span) or _has_blocked_tail(text, span[1]):
                        continue
                    current = bindings.get(span)
                    if current is None or priority < current[0]:
                        bindings[span] = (priority, code)
        for (start, end), (_priority, code) in sorted(bindings.items()):
            evidence = text[start:end]
            value = parse_number(evidence)
            low, high = RULE_PROXIMITY_VALUE_RANGES[code]
            if not low <= value <= high:
                continue
            unit = RULE_PROXIMITY_DEFAULT_UNITS[code]
            yield (code, evidence, f"{format_number(value)} {unit}", evidence)

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

    def _brand_model_values(self, text: str) -> Iterator[str]:
        """Модель после каждого найденного бренда (словарь, границы слов).

        Значение, целиком входящее в другое (суффикс после бренда-в-бренде:
        «Redmi 10C» внутри модели от «Xiaomi»), пропускается — остаётся самое
        полное название.
        """
        if self._brand_re is None or self._brand_vocab is None:
            return
        values: list[str] = []
        for match in self._brand_re.finditer(text):
            if self._brand_vocab.resolve(match.group(0)) is None:
                continue  # стоп-слово словаря: бренда нет — и модели тоже
            model = _model_value_after_brand(text, match)
            if model is not None:
                values.append(model)
        for value in values:
            covered = any(other != value and f" {value}" in f" {other}" for other in values)
            if not covered:
                yield value

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

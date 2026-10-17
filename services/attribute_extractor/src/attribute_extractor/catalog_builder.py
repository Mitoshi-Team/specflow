"""Сборка каталога полей и блоклиста из seed с опциональным обогащением по EDA.

Ядро генератора ``scripts/build_field_catalog.py``: детерминированно строит
структуру каталога из ``field_catalog_seed`` и, при наличии
``param_stats.parquet`` (результат ``EDA/src/catalog.py``), дополняет синонимы
и блоклист наблюдаемыми именами атрибутов.
"""

from __future__ import annotations

import re
from pathlib import Path

from attribute_extractor.field_catalog_seed import (
    BLOCKLIST_SEED,
    CANONICAL_FIELDS,
    FIELD_CATALOG_VERSION,
    FieldSeed,
)

DEFAULT_ENRICH_MIN_COUNT = 20
"""Минимальная частота имени атрибута для попадания в синонимы/блоклист."""

_WORD_BOUNDARY = r"[0-9a-zа-яё]"
"""Класс «словесных» символов для границ целых слов (русский/латиница/цифры)."""


def _as_whole_word(phrase: str) -> re.Pattern[str]:
    """Регулярка для поиска фразы как целых слов (не как подстроки)."""
    pattern = rf"(?<!{_WORD_BOUNDARY}){re.escape(phrase)}(?!{_WORD_BOUNDARY})"
    return re.compile(pattern)


def _entry_from_seed(seed: FieldSeed) -> dict:
    return {
        "code": seed.code,
        "name_ru": seed.name_ru,
        "synonyms": list(seed.synonyms),
        "value_type": seed.value_type,
        "unit": seed.unit,
        "is_new_field": False,
    }


def build_catalog() -> dict:
    """Базовый каталог из seed (без обогащения)."""
    return {
        "version": FIELD_CATALOG_VERSION,
        "entries": [_entry_from_seed(seed) for seed in CANONICAL_FIELDS],
    }


def _field_phrases() -> list[tuple[str, str, re.Pattern[str]]]:
    """Список (код, фраза, регулярка целых слов) по всем полям и синонимам."""
    phrases: list[tuple[str, str, re.Pattern[str]]] = []
    for seed in CANONICAL_FIELDS:
        for phrase in (seed.name_ru, *seed.synonyms):
            phrases.append((seed.code, phrase, _as_whole_word(phrase.casefold())))
    return phrases


def load_param_stats(path: str | Path) -> list[tuple[str, int]]:
    """Читает ``param_stats.parquet`` и возвращает пары (имя, частота).

    pandas/pyarrow импортируются локально, чтобы базовый генератор не требовал
    тяжёлых зависимостей.
    """
    import pandas as pd

    frame = pd.read_parquet(path, columns=["param", "n"])
    return [(str(row.param), int(row.n)) for row in frame.itertuples(index=False)]


def enrich_catalog(catalog: dict, param_stats: list[tuple[str, int]], min_count: int) -> None:
    """Дополняет синонимы полей наблюдаемыми именами (in-place, детерминированно)."""
    phrases = _field_phrases()
    by_code = {entry["code"]: entry for entry in catalog["entries"]}
    for name, count in sorted(param_stats, key=lambda item: (-item[1], item[0])):
        if count < min_count:
            continue
        low = name.casefold()
        for code, _phrase, pattern in phrases:
            if pattern.search(low):
                synonyms = by_code[code]["synonyms"]
                if name not in synonyms:
                    synonyms.append(name)
                break


def collect_blocklist(param_stats: list[tuple[str, int]], min_count: int) -> list[str]:
    """Кандидаты в блоклист: наблюдаемые имена, содержащие стоп-слова EDA."""
    extra = []
    for name, count in sorted(param_stats, key=lambda item: (-item[1], item[0])):
        low = name.casefold()
        if count < min_count:
            continue
        if any(token in low for token in BLOCKLIST_SEED) and name not in extra:
            extra.append(name)
    return extra


def build_blocklist(
    param_stats: list[tuple[str, int]] | None = None, min_count: int = 0
) -> list[str]:
    """Блоклист: seed-стоп-слова плюс (опц.) кандидаты из наблюдаемых имён."""
    entries = list(BLOCKLIST_SEED)
    if param_stats:
        for candidate in collect_blocklist(param_stats, min_count):
            if candidate.casefold() not in {e.casefold() for e in entries}:
                entries.append(candidate)
    return entries


def build(
    param_stats_path: str | Path | None = None,
    min_count: int = DEFAULT_ENRICH_MIN_COUNT,
) -> tuple[dict, list[str]]:
    """Собрать (каталог, блоклист); при ``param_stats_path`` — с обогащением."""
    catalog = build_catalog()
    param_stats = load_param_stats(param_stats_path) if param_stats_path else None
    if param_stats:
        enrich_catalog(catalog, param_stats, min_count)
    return catalog, build_blocklist(param_stats, min_count)

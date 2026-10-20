"""Сборка реестра схем категорий из статистики каталога (EDA/cache).

Ядро генератора ``scripts/build_category_schemas.py``: по таблицам EDA
(результат ``EDA/src/run.py``)

- ``categories.parquet``   — ``category_id`` → имя категории;
- ``offers_flat.parquet``  — карточки категории и vendor/model-колонки;
- ``cat_attr.parquet``     — заполненность (fill rate) атрибута по категории;
- ``param_stats.parquet``  — частоты имён атрибутов (обогащение синонимов и
  блоклиста каталога полей, как в ``catalog_builder``),

строит ``CategorySchema`` для каждой категории:

- имена seller-параметров резолвятся в 9 канонических кодов через
  ``FieldResolver`` (Этап 5); нераспознанные и шумовые имена отбрасываются;
- поле с fill rate >= ``CATEGORY_SCHEMA_REQUIRED_SHARE`` становится
  обязательным (управляет rules-fallback, Этап 7), с меньшей ненулевой
  долей — опциональным;
- категории меньше ``CATEGORY_SCHEMA_MIN_CARDS`` пропускаются: их карточки
  получают generic-fallback.

Инвариант text-only: в схему попадают только описания полей (код, имя, тип,
единица, синонимы-имена); значения seller-атрибутов в артефакт не попадают и
в извлечение не передаются. Персист каталога полей не выполняется —
хранилищу резолвера передаётся временный путь, ``data/field_catalog.json``
офлайн-сборка не затирает.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from attribute_extractor import catalog_builder
from attribute_extractor.catalog_store import CatalogStore
from attribute_extractor.constants import (
    CATEGORY_SCHEMA_MIN_CARDS,
    CATEGORY_SCHEMA_REQUIRED_SHARE,
    CATEGORY_SCHEMA_VERSION,
)
from attribute_extractor.field_catalog_seed import CANONICAL_FIELDS
from attribute_extractor.fields import FieldBlocklist, FieldCatalog, FieldResolver
from specflow_contracts import Attribute, AttributeValueType, CategorySchema

CANONICAL_CODES: frozenset[str] = frozenset(seed.code for seed in CANONICAL_FIELDS)
"""Коды, допустимые в схеме категории (авто-добавленные поля не входят)."""


@dataclass
class _CategoryCards:
    """Счётчики карточек категории из ``offers_flat.parquet``."""

    total: int = 0
    vendor_present: int = 0
    model_present: int = 0


def _load_categories(path: str | Path) -> dict[str, str]:
    """``category_id`` → имя категории (пропуск битых/пустых строк)."""
    import pandas as pd

    frame = pd.read_parquet(path, columns=["category_id", "category_name"])
    categories: dict[str, str] = {}
    for row in frame.itertuples(index=False):
        if pd.isna(row.category_id) or pd.isna(row.category_name):
            continue
        category_id = str(row.category_id).strip()
        name = str(row.category_name).strip()
        if category_id and name:
            categories[category_id] = name
    return categories


def _load_cards(path: str | Path) -> dict[str, _CategoryCards]:
    """Число карточек и заполненность vendor/model по категориям."""
    import pandas as pd

    frame = pd.read_parquet(path, columns=["category_id", "vendor", "model"])
    cards: dict[str, _CategoryCards] = {}
    for row in frame.itertuples(index=False):
        if pd.isna(row.category_id):
            continue
        stats = cards.setdefault(str(row.category_id), _CategoryCards())
        stats.total += 1
        if not pd.isna(row.vendor) and str(row.vendor).strip():
            stats.vendor_present += 1
        if not pd.isna(row.model) and str(row.model).strip():
            stats.model_present += 1
    return cards


def _load_cat_attr(path: str | Path) -> list[tuple[str, str, float]]:
    """Строки ``(category_id, param, fill_rate)`` из ``cat_attr.parquet``."""
    import pandas as pd

    frame = pd.read_parquet(path, columns=["category_id", "param", "fill_rate"])
    rows: list[tuple[str, str, float]] = []
    for row in frame.itertuples(index=False):
        if pd.isna(row.category_id) or pd.isna(row.param):
            continue
        category_id = str(row.category_id).strip()
        param = str(row.param).strip()
        if category_id and param:
            rows.append((category_id, param, float(row.fill_rate)))
    return rows


def _make_resolver(catalog_data: dict, blocklist: list[str], tmp_dir: Path) -> FieldResolver:
    """FieldResolver по каталогу (seed + обогащение по param_stats) без персиста.

    Резолвер авто-добавляет неизвестные имена как новые поля в память;
    в схему они всё равно не входят (``_param_codes`` отбрасывает их), а
    ``persist_new_fields=False`` отключает перезапись JSON-хранилища при
    каждом добавлении — на ~10k уникальных имён это часы перечитываний
    вместо секунд. Хранилище указывает во временный каталог и удаляется
    после сборки, ``data/field_catalog.json`` офлайн-сборка не затирает.
    """
    store = CatalogStore(tmp_dir / "field_catalog.json", tmp_dir / "field_blocklist.txt")
    return FieldResolver(
        catalog=FieldCatalog.from_dict(catalog_data),
        blocklist=FieldBlocklist(blocklist),
        store=store,
        persist_new_fields=False,
    )


def _param_codes(params: Iterable[str], resolver: FieldResolver) -> dict[str, str | None]:
    """Резолв имён seller-параметров в канонические коды (None — не каноническое).

    Обход отсортирован, чтобы авто-добавление резолвером неизвестных имён
    (в память, без персиста) не зависело от порядка строк в parquet.
    """
    codes: dict[str, str | None] = {}
    for param in sorted(set(params)):
        match = resolver.resolve(param)
        code = match.matched_code
        if match.blocked or match.is_new_field or code not in CANONICAL_CODES:
            code = None
        codes[param] = code
    return codes


def _field_shares(
    cat_attr: list[tuple[str, str, float]],
    codes: dict[str, str | None],
    cards: dict[str, _CategoryCards],
) -> dict[tuple[str, str], float]:
    """Доля карточек категории с полем: ключ ``(category_id, код)``.

    Несколько seller-параметров могут вести в один код: берётся max —
    объединение «есть хотя бы один параметр» по маргиналам ``cat_attr`` не
    вычисляется, max даёт консервативную оценку. brand/model дополнительно
    учитывают vendor/model-колонки ``offers_flat`` (это поля карточки, а не
    seller-параметры: EDA считает их заполненность отдельно).
    """
    shares: dict[tuple[str, str], float] = {}
    for category_id, param, fill_rate in cat_attr:
        code = codes.get(param)
        if code is None:
            continue
        key = (category_id, code)
        if fill_rate > shares.get(key, 0.0):
            shares[key] = fill_rate
    for category_id, stats in cards.items():
        if not stats.total:
            continue
        vendor_share = stats.vendor_present / stats.total
        if vendor_share > shares.get((category_id, "brand"), 0.0):
            shares[(category_id, "brand")] = vendor_share
        model_share = stats.model_present / stats.total
        if model_share > shares.get((category_id, "model"), 0.0):
            shares[(category_id, "model")] = model_share
    return shares


def _assemble(
    categories: dict[str, str],
    cards: dict[str, _CategoryCards],
    shares: dict[tuple[str, str], float],
    synonyms_by_code: dict[str, list[str]],
    *,
    required_share: float,
    min_cards: int,
) -> list[CategorySchema]:
    """Собрать схемы категорий (детерминированный порядок: имя, затем id)."""
    schemas: list[CategorySchema] = []
    for category_id, name in categories.items():
        stats = cards.get(category_id)
        if stats is None or stats.total < min_cards:
            continue
        required: list[Attribute] = []
        optional: list[Attribute] = []
        for seed in CANONICAL_FIELDS:
            share = shares.get((category_id, seed.code), 0.0)
            if share <= 0.0:
                continue
            attribute = Attribute(
                code=seed.code,
                value_type=AttributeValueType(seed.value_type),
                name_ru=seed.name_ru,
                is_required=share >= required_share,
                unit=seed.unit,
                synonyms=synonyms_by_code.get(seed.code) or None,
            )
            (required if attribute.is_required else optional).append(attribute)
        if not required and not optional:
            # Категория без единого канонического поля — схема бесполезна,
            # карточки получают generic-fallback.
            continue
        schemas.append(
            CategorySchema(
                category=name,
                category_id=category_id,
                schema_version=CATEGORY_SCHEMA_VERSION,
                required_attributes=required,
                optional_attributes=optional,
            )
        )
    return sorted(
        schemas,
        key=lambda schema: (schema.category.casefold(), schema.category_id or ""),
    )


def build(
    *,
    categories_path: str | Path,
    offers_path: str | Path,
    cat_attr_path: str | Path,
    param_stats_path: str | Path | None = None,
    required_share: float = CATEGORY_SCHEMA_REQUIRED_SHARE,
    min_cards: int = CATEGORY_SCHEMA_MIN_CARDS,
) -> dict:
    """Собрать артефакт реестра ``{"version": ..., "schemas": [...]}``.

    ``param_stats_path`` не обязателен: без него каталог полей остаётся в
    seed-виде (без обогащения синонимами наблюдаемых имён).
    """
    catalog_data, blocklist = catalog_builder.build(param_stats_path=param_stats_path)
    categories = _load_categories(categories_path)
    cards = _load_cards(offers_path)
    cat_attr = _load_cat_attr(cat_attr_path)
    with tempfile.TemporaryDirectory(prefix="category_schemas_") as tmp_dir:
        resolver = _make_resolver(catalog_data, blocklist, Path(tmp_dir))
        codes = _param_codes((param for _, param, _ in cat_attr), resolver)
    shares = _field_shares(cat_attr, codes, cards)
    synonyms_by_code = {
        entry["code"]: list(entry.get("synonyms") or [])
        for entry in catalog_data["entries"]
        if entry.get("code")
    }
    schemas = _assemble(
        categories,
        cards,
        shares,
        synonyms_by_code,
        required_share=required_share,
        min_cards=min_cards,
    )
    return {
        "version": CATEGORY_SCHEMA_VERSION,
        "schemas": [schema.model_dump(mode="json") for schema in schemas],
    }


def save(payload: dict, path: str | Path) -> None:
    """Атомарно записать артефакт (временный файл + ``os.replace``, как в CatalogStore)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    os.replace(tmp, target)

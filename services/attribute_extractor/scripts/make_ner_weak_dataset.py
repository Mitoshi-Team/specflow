"""Генерация weak-датасета для NER (distant supervision, Этап 4).

Примеры:

    python scripts/make_ner_weak_dataset.py --max-per-category 4000
    python scripts/make_ner_weak_dataset.py --val-share 0.1 --seed 20261017

Источники: ``EDA/dataset/skus.pkl`` (YML-каталог: офферы с параметрами
продавца) и ``EDA/dataset/sku_desc.parquet`` (тексты карточек). Карточки без
seller-параметров не участвуют: слабая разметка приходит из структурных
полей. Выход — ``data/ner/weak.jsonl`` и split ``train.jsonl``/``val.jsonl``
(каталог ``data/`` генерируется, в репозиторий не попадает).
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_SRC_DIR = _SERVICE_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import pandas as pd  # noqa: E402

from attribute_extractor import weak_markup  # noqa: E402
from attribute_extractor.catalog_store import CatalogStore  # noqa: E402
from attribute_extractor.constants import (  # noqa: E402
    DEFAULT_FIELD_BLOCKLIST_PATH,
    DEFAULT_FIELD_CATALOG_PATH,
    NER_LABEL_PROPERTY,
)
from attribute_extractor.fields import FieldResolver  # noqa: E402

_WEAK_DIR = Path("data") / "ner"
FOCUS_CATEGORIES = (
    "Смартфоны",
    "iPhone",
    "Ноутбуки",
    "Планшеты",
    "Телевизоры",
    "Мониторы",
    "Наушники",
    "Роботы-пылесосы",
)
DEFAULT_SEED = 20261017
DEFAULT_MAX_PER_CATEGORY = 4000
DEFAULT_VAL_SHARE = 0.1
TOP_UNCODED_PARAMS_LIMIT = 20
# В YML бренд и модель лежат не в param, а в отдельных полях оффера;
# для слабой разметки они подаются как псевдопараметры с именами,
# которые резолвятся в канонические поля brand/model.
VENDOR_PARAM_NAME = "Бренд"
MODEL_PARAM_NAME = "Модель"


class _RestrictedUnpickler(pickle.Unpickler):
    """Десериализация только встроенных типов: датасет может быть подменён."""

    def find_class(self, module: str, name: str) -> Any:
        raise pickle.UnpicklingError(f"Импорт классов запрещён: {module}.{name}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Собрать weak-датасет для NER.")
    parser.add_argument("--dataset-dir", type=Path, default=Path("EDA/dataset"))
    parser.add_argument("--out-dir", type=Path, default=_WEAK_DIR)
    parser.add_argument(
        "--max-per-category",
        type=int,
        default=DEFAULT_MAX_PER_CATEGORY,
        help="Максимум записей на категорию (балансировка классов).",
    )
    parser.add_argument("--val-share", type=float, default=DEFAULT_VAL_SHARE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args(argv)


def load_offers(dataset_dir: Path) -> dict[str, dict[str, Any]]:
    """Сырые YML-офферы по sku (ограниченная десериализация).

    Офферы возвращаются без разбора: параметры и vendor/model нужны только
    для отобранных карточек, а офферов в каталоге более полумиллиона.
    """
    with (dataset_dir / "skus.pkl").open("rb") as handle:
        raw = _RestrictedUnpickler(handle).load()
    offers = raw["yml_catalog"]["shop"]["offers"]["offer"]
    return {str(offer["@id"]): offer for offer in offers}


def offer_params(offer: dict[str, Any]) -> list[dict[str, str]]:
    """Параметры оффера: seller-параметры плюс vendor/model как псевдопараметры."""
    params = weak_markup.parse_seller_params(offer.get("param", []))
    if offer.get("vendor"):
        params.append({"name": VENDOR_PARAM_NAME, "value": str(offer["vendor"])})
    if offer.get("model"):
        params.append({"name": MODEL_PARAM_NAME, "value": str(offer["model"])})
    return params


def load_categories(dataset_dir: Path) -> dict[str, str]:
    """Категория (название) по sku: offers_flat.parquet + categories.parquet."""
    offers_flat = pd.read_parquet(dataset_dir.parent / "cache" / "offers_flat.parquet")
    cats = pd.read_parquet(dataset_dir.parent / "cache" / "categories.parquet")
    names = dict(
        zip(
            cats["category_id"].astype(str),
            cats["category_name"].astype(str),
            strict=False,
        )
    )
    return {
        str(row.sku_id): names.get(str(row.category_id), "")
        for row in offers_flat.itertuples(index=False)
    }


def select_cards(
    dataset_dir: Path,
    offers: dict[str, dict[str, Any]],
    categories: dict[str, str],
    max_per_category: int,
) -> pd.DataFrame:
    """Векторный отбор карточек фокус-категорий (до N на категорию).

    Полный перебор 1.17M карточек в Python занимает часы; здесь один
    векторный проход: соединение с категориями, фильтр фокуса, фильтр
    карточек с параметрами и head(N) на категорию в порядке файла
    (детерминированно).
    """
    cards = pd.read_parquet(dataset_dir / "sku_desc.parquet")
    cards["sku_id"] = cards["sku_id"].astype(str)
    cards["title"] = cards["title"].fillna("")
    cards["description"] = cards["description"].fillna("")
    cat_frame = pd.DataFrame(
        [(sku, name) for sku, name in categories.items() if name],
        columns=["sku_id", "category_name"],
    )
    merged = cards.merge(cat_frame, on="sku_id", how="inner")
    merged = merged[merged["category_name"].isin(FOCUS_CATEGORIES)]
    merged = merged[merged["sku_id"].isin(offers)]
    return merged.groupby("category_name", sort=False).head(max_per_category)


def build_resolver() -> FieldResolver:
    """Резолвер поверх боевого каталога, без персиста новых полей.

    Слабая разметка не должна дополнять боевой каталог: параметры вне девяти
    канонических полей остаются только в памяти и дают некодированные спаны
    (``attribute_code=None``) — канон назначает полю ручной аудит.
    """
    return FieldResolver(
        store=CatalogStore(DEFAULT_FIELD_CATALOG_PATH, DEFAULT_FIELD_BLOCKLIST_PATH),
        persist_new_fields=False,
    )


def generate(
    dataset_dir: Path,
    out_dir: Path,
    *,
    max_per_category: int = DEFAULT_MAX_PER_CATEGORY,
    val_share: float = DEFAULT_VAL_SHARE,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Собрать weak-датасет и split; вернуть статистику по полям.

    Помимо канонических полей размечаются неканонические параметры
    (``include_uncoded=True``): их спаны несут ``attribute_code=None``.
    ``top_uncoded_params`` показывает, какие имена дали некодированные
    PROPERTY-спаны, — основа для пополнения блоклиста вторым проходом.
    """
    resolver = build_resolver()
    resolve_cache: dict[str, weak_markup.ParamResolution] = {}
    counts: Counter[str] = Counter()
    uncoded_names: Counter[str] = Counter()
    property_spans_total = 0
    property_spans_uncoded = 0
    records_with_uncoded = 0
    per_category: Counter[str] = Counter()
    records: list[weak_markup.WeakRecord] = []
    offers = load_offers(dataset_dir)
    categories = load_categories(dataset_dir)
    selected = select_cards(dataset_dir, offers, categories, max_per_category)
    print(f"отобрано карточек: {len(selected)}", flush=True)
    for row in selected.itertuples(index=False):
        record = weak_markup.build_record(
            str(row.title),
            str(row.description),
            offer_params(offers.get(row.sku_id, {})),
            resolver,
            sku_id=row.sku_id,
            category_name=row.category_name,
            resolve_cache=resolve_cache,
            include_uncoded=True,
        )
        if record is None:
            continue
        records.append(record)
        per_category[row.category_name] += 1
        has_uncoded = False
        for span in record.spans:
            if span.label != NER_LABEL_PROPERTY:
                continue
            property_spans_total += 1
            if span.attribute_code is None:
                property_spans_uncoded += 1
                has_uncoded = True
                uncoded_names[span.parameter_name or ""] += 1
            else:
                counts[span.attribute_code] += 1
        if has_uncoded:
            records_with_uncoded += 1
    train, val = weak_markup.stratified_split(records, val_share=val_share, seed=seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, split in (("weak", records), ("train", train), ("val", val)):
        with (out_dir / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
            for record in split:
                handle.write(json.dumps(record.as_dict(), ensure_ascii=False) + "\n")
    return {
        "records": len(records),
        "train": len(train),
        "val": len(val),
        "property_spans_total": property_spans_total,
        "property_spans_uncoded": property_spans_uncoded,
        "records_with_uncoded": records_with_uncoded,
        "property_spans_by_code": dict(sorted(counts.items())),
        "top_uncoded_params": dict(uncoded_names.most_common(TOP_UNCODED_PARAMS_LIMIT)),
        "per_category": dict(sorted(per_category.items())),
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not (args.dataset_dir / "skus.pkl").exists():
        print(f"нет skus.pkl в {args.dataset_dir}", file=sys.stderr)
        return 1
    stats = generate(
        args.dataset_dir,
        args.out_dir,
        max_per_category=args.max_per_category,
        val_share=args.val_share,
        seed=args.seed,
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

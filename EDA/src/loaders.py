"""Загрузка источников данных с кэшированием тяжёлых производных таблиц."""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from . import config


def _cache(name: str) -> Path:
    return config.CACHE_DIR / name


def save_json(name: str, obj) -> None:
    with open(_cache(name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)


def load_json(name: str):
    with open(_cache(name), encoding="utf-8") as f:
        return json.load(f)


def load_cards(columns: list[str] | None = None) -> pd.DataFrame:
    return pd.read_parquet(config.CARDS_PATH, columns=columns)


def load_raw_offers() -> dict:
    """Возвращает распакованный YML-каталог (dict)."""
    with open(config.SKUS_PATH, "rb") as f:
        return pickle.load(f)


def build_catalog_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Строит offers_flat и categories, кэширует в parquet. Идемпотентно."""
    offers_path = _cache("offers_flat.parquet")
    cats_path = _cache("categories.parquet")
    if offers_path.exists() and cats_path.exists():
        return pd.read_parquet(offers_path), pd.read_parquet(cats_path)

    raw = load_raw_offers()
    shop = raw["yml_catalog"]["shop"]
    offers = shop["offers"]["offer"]
    cats = shop["categories"]["category"]

    cat_rows = [(str(c["@id"]), c["#text"], c.get("@parentId")) for c in cats]
    cat_df = pd.DataFrame(cat_rows, columns=["category_id", "category_name", "parent_id"])
    cat_df.to_parquet(cats_path, index=False)

    rows = []
    for o in offers:
        c = o.get("categories")
        cid = c.get("categoryId") if isinstance(c, dict) else None
        rows.append(
            (
                str(o["@id"]),
                str(cid) if cid is not None else None,
                o.get("vendor"),
                o.get("model"),
                o.get("name"),
                o.get("@available"),
                len(o.get("param", [])),
            )
        )
    offer_df = pd.DataFrame(
        rows,
        columns=["sku_id", "category_id", "vendor", "model", "name", "available", "n_params"],
    )
    offer_df.to_parquet(offers_path, index=False)
    return offer_df, cat_df


def iter_clicks_batches(columns: list[str] | None = None, batch_size: int | None = None):
    """Стриминг query_clicks.parquet батчами (pandas DataFrame)."""
    batch_size = batch_size or config.CLICKS_BATCH
    pf = pq.ParquetFile(config.CLICKS_PATH)
    for batch in pf.iter_batches(batch_size=batch_size, columns=columns):
        yield batch.to_pandas()


def clicks_meta() -> dict:
    pf = pq.ParquetFile(config.CLICKS_PATH)
    return {"num_rows": pf.metadata.num_rows, "num_row_groups": pf.num_row_groups}

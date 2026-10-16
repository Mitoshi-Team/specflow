"""Анализ трафика (query_clicks.parquet): цены, позиции, запросы, категории."""

from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from . import config, loaders

QUERY_COL = "toValidUTF8(query_text)"
SUBJ_COL = "sku_subject_id"


def run() -> dict:
    meta = loaders.clicks_meta()
    n = meta["num_rows"]

    # --- числовые колонки целиком ---
    df = pd.read_parquet(
        config.CLICKS_PATH,
        columns=["sku_id", SUBJ_COL, "sku_price", "sku_position"],
    )
    price = df["sku_price"].to_numpy()
    finite = np.isfinite(price)
    price_f = price[finite]
    quantiles = np.quantile(price_f, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 0.999])

    subj_cnt = df[SUBJ_COL].value_counts()
    pos_cnt = df["sku_position"].value_counts().sort_index()

    summary = {
        "n_rows": int(n),
        "n_unique_sku": int(df.sku_id.nunique()),
        "n_unique_subject": int(df[SUBJ_COL].nunique()),
        "price_mean": float(price_f.mean()),
        "price_median": float(np.median(price_f)),
        "price_min": float(price_f.min()),
        "price_max": float(price_f.max()),
        "price_zero_share": float((price == 0).mean()),
        "price_negative": int((price < 0).sum()),
        "price_quantiles": {
            q: float(v) for q, v in zip([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 0.999], quantiles)
        },
        "position_max": int(pos_cnt.index.max()),
        "position_0_share": float(pos_cnt.get(0, 0) / n),
        "position_counts_head": pos_cnt.head(20).to_dict(),
    }

    # --- запросы (стриминг) ---
    qcnt: Counter = Counter()
    for batch in loaders.iter_clicks_batches(columns=[QUERY_COL]):
        for v, c in batch[QUERY_COL].value_counts().head(500).items():
            qcnt[v] += c
    queries_top = qcnt.most_common(config.TOP_N)
    pd.DataFrame(queries_top, columns=["query", "clicks"]).to_csv(
        config.RESULTS_DIR / "top_queries.csv", index=False
    )

    # --- категории с названиями ---
    _, cat_df = loaders.build_catalog_tables()
    name = dict(zip(cat_df.category_id.astype(str), cat_df.category_name))
    subj_df = subj_cnt.rename_axis("category_id").reset_index(name="clicks")
    subj_df["category_id"] = subj_df["category_id"].astype(str)
    subj_df["category_name"] = subj_df["category_id"].map(name)
    subj_df["share"] = subj_df["clicks"] / n
    subj_df.head(50).to_csv(config.RESULTS_DIR / "top_categories_traffic.csv", index=False)

    # --- сэмпл цен для гистограммы ---
    rng = np.random.default_rng(config.RANDOM_SEED)
    idx = rng.choice(len(price_f), size=min(500_000, len(price_f)), replace=False)
    pd.DataFrame({"price": price_f[idx]}).to_parquet(
        config.CACHE_DIR / "price_sample.parquet", index=False
    )

    # уникальные sku для анализа связей
    pd.DataFrame({"sku_id": df.sku_id.unique().astype(str)}).to_parquet(
        config.CACHE_DIR / "clicks_skus.parquet", index=False
    )

    summary["top_queries"] = queries_top[:15]
    summary["top_categories"] = [
        {
            "category_id": r.category_id,
            "name": r.category_name,
            "clicks": int(r.clicks),
            "share": float(r.share),
        }
        for r in subj_df.head(20).itertuples()
    ]

    loaders.save_json("traffic_summary.json", summary)
    return summary

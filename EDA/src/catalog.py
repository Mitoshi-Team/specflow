"""Анализ каталога skus.pkl: категории, параметры, целевые атрибуты, нормализация."""

from __future__ import annotations

import re
from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from . import config, loaders

NUM_RE = re.compile(r"^[+-]?\d+([.,]\d+)?$")
SEARCH_SUFFIX = "_search"

# разбор «число + единица» для памяти/экрана
STORAGE_RE = re.compile(
    r"(\d+([.,]\d+)?)\s*(ТБ|TB|ГБ|GB|МБ|MB|гб|gb|мб)(?![а-яa-z])", re.IGNORECASE
)
BARE_NUM_RE = re.compile(r"^\d+([.,]\d+)?$")
DIAG_INCH_RE = re.compile(r"(\d+([.,]\d+)?)\s*(?:\"|”|дюйм|inch|in\b)", re.IGNORECASE)
DIAG_CM_RE = re.compile(r"(\d+([.,]\d+)?)\s*(?:см|cm)", re.IGNORECASE)


def norm_attr(name: str) -> str:
    return name[: -len(SEARCH_SUFFIX)] if name.endswith(SEARCH_SUFFIX) else name


def _norm_color(v: str) -> str:
    return v.strip().lower().replace("ё", "е")


def _alias_index() -> dict[str, str]:
    idx: dict[str, str] = {}
    for code, meta in config.TARGET_ATTRIBUTES.items():
        for a in meta["aliases"]:
            idx[a.lower()] = code
    return idx


def _focus_category_ids(cat_df: pd.DataFrame, offer_df: pd.DataFrame) -> dict[str, str]:
    cnt = offer_df.category_id.value_counts()
    out: dict[str, str] = {}
    for name in config.FOCUS_CATEGORIES:
        m = cat_df[cat_df.category_name == name]
        if m.empty:
            continue
        ids = m.category_id.tolist()
        best = max(ids, key=lambda c: cnt.get(c, 0))
        out[name] = best
    return out


def run() -> dict:
    offer_df, cat_df = loaders.build_catalog_tables()
    raw = loaders.load_raw_offers()
    offers = raw["yml_catalog"]["shop"]["offers"]["offer"]

    focus_ids = _focus_category_ids(cat_df, offer_df)
    focus_inv = {v: k for k, v in focus_ids.items()}
    alias_idx = _alias_index()

    raw_name_cnt = Counter()
    name_cnt = Counter()
    name_cats = defaultdict(set)
    name_units = defaultdict(Counter)
    name_vals = defaultdict(Counter)
    name_numeric = Counter()
    name_noval = Counter()
    cat_attr = Counter()  # (cid, base) -> offers count
    cat_offers = Counter()
    focus_attr_vals = defaultdict(Counter)  # (cid, base) -> values (focus cats)
    focus_attr_units = defaultdict(Counter)

    # накопители для анализа нормализации
    storage_values = Counter()
    diagonal_values = Counter()
    color_values = Counter()
    unit_spellings = defaultdict(Counter)

    for o in offers:
        cats_ = o.get("categories")
        cid = cats_.get("categoryId") if isinstance(cats_, dict) else None
        cid = str(cid) if cid is not None else None
        is_focus = cid in focus_inv
        if cid is not None:
            cat_offers[cid] += 1
        seen_base = set()
        for p in o["param"]:
            if not isinstance(p, dict):
                continue
            nm = p.get("@name")
            if nm is None:
                continue
            raw_name_cnt[nm] += 1
            base = norm_attr(nm)
            name_cnt[base] += 1
            name_cats[base].add(cid)
            unit = p.get("@unit")
            if unit:
                name_units[base][unit] += 1
                for canon, syns in config.UNIT_SYNONYMS.items():
                    if unit in syns:
                        unit_spellings[canon][unit] += 1
            val = p.get("#text")
            if val is None:
                name_noval[base] += 1
                continue
            val = str(val).strip()
            if NUM_RE.match(val):
                name_numeric[base] += 1
            if len(name_vals[base]) < config.PARAM_VALUE_CAP:
                name_vals[base][val] += 1

            if base not in seen_base:
                seen_base.add(base)
                cat_attr[(cid, base)] += 1
                if is_focus:
                    focus_attr_units[(cid, base)][unit or ""] += 1
            if is_focus:
                focus_attr_vals[(cid, base)][val] += 1

            # нормализация значений
            code = alias_idx.get(base.lower())
            if code == "storage":
                storage_values[val] += 1
            elif code == "diagonal":
                diagonal_values[val] += 1
            elif code == "color":
                color_values[val] += 1

    # --- сводка по параметрам ---
    rows = []
    for base, c in name_cnt.items():
        vc = name_vals[base]
        rows.append(
            (
                base,
                c,
                len(name_cats[base]),
                len(vc),
                name_numeric[base] / c,
                name_noval[base] / c,
                name_units[base].most_common(1)[0][0] if name_units[base] else "",
                " | ".join(f"{v} ({k})" for v, k in vc.most_common(3)),
            )
        )
    param_stats = pd.DataFrame(
        rows,
        columns=[
            "param",
            "n",
            "n_cats",
            "n_vals",
            "num_share",
            "noval_share",
            "top_unit",
            "top_vals",
        ],
    ).sort_values("n", ascending=False)
    param_stats.to_parquet(config.CACHE_DIR / "param_stats.parquet", index=False)

    # --- сводка по каталогу ---
    n_params_per_offer = offer_df.n_params
    summary = {
        "n_offers": int(len(offer_df)),
        "n_categories_total": int(len(cat_df)),
        "n_categories_used": int(offer_df.category_id.nunique()),
        "n_distinct_param_names": int(param_stats.shape[0]),
        "total_param_assignments": int(sum(name_cnt.values())),
        "params_per_offer_mean": float(n_params_per_offer.mean()),
        "params_per_offer_median": float(n_params_per_offer.median()),
        "params_per_offer_p95": float(n_params_per_offer.quantile(0.95)),
        "params_per_offer_max": int(n_params_per_offer.max()),
        "vendor_fill": float(offer_df.vendor.notna().mean()),
        "model_fill": float(offer_df.model.notna().mean()),
        "available_true": float((offer_df.available == "true").mean()),
        "search_suffixed_share": float(
            sum(c for k, c in raw_name_cnt.items() if k.endswith(SEARCH_SUFFIX))
            / sum(raw_name_cnt.values())
        ),
        "n_unit_spellings": {k: len(v) for k, v in unit_spellings.items()},
        "unit_spellings": {k: v.most_common(10) for k, v in unit_spellings.items()},
    }

    # доля _search среди сырых имён (до нормализации)
    summary["n_distinct_param_names_raw"] = int(len(raw_name_cnt))
    summary["long_tail_params"] = {
        "lt_5": int((param_stats.n < 5).sum()),
        "lt_10": int((param_stats.n < 10).sum()),
        "lt_100": int((param_stats.n < 100).sum()),
        "gt_10000": int((param_stats.n > 10000).sum()),
    }

    # --- топ атрибутов по категориям ---
    cat_name = dict(zip(cat_df.category_id, cat_df.category_name))
    cat_attr_rows = []
    for (cid, base), c in cat_attr.items():
        no = cat_offers[cid]
        if no == 0:
            continue
        cat_attr_rows.append((cid, cat_name.get(cid), base, c, c / no))
    cat_attr_df = pd.DataFrame(
        cat_attr_rows, columns=["category_id", "category_name", "param", "n_offers", "fill_rate"]
    )
    cat_attr_df.to_parquet(config.CACHE_DIR / "cat_attr.parquet", index=False)

    # --- целевые категории: атрибуты и значения ---
    focus_rows = []
    for cid, cname in focus_inv.items():
        no = cat_offers[cid]
        # brand/model
        v = offer_df[offer_df.category_id == cid]
        focus_rows.append(
            (
                cname,
                cid,
                "brand (vendor)",
                int(v.vendor.notna().sum()),
                v.vendor.notna().mean(),
                v.vendor.nunique(),
                "",
            )
        )
        focus_rows.append(
            (
                cname,
                cid,
                "model",
                int(v.model.notna().sum()),
                v.model.notna().mean(),
                v.model.nunique(),
                "",
            )
        )
        pairs = [(b, cat_attr[(cid, b)]) for (c, b) in cat_attr if c == cid]
        for base, c in sorted(pairs, key=lambda x: -x[1])[:25]:
            vals = focus_attr_vals.get((cid, base), Counter())
            top = " | ".join(f"{k} ({n})" for k, n in vals.most_common(3))
            focus_rows.append((cname, cid, base, c, c / no, len(vals), top))
    focus_df = pd.DataFrame(
        focus_rows,
        columns=[
            "category_name",
            "category_id",
            "param",
            "n_offers",
            "fill_rate",
            "n_distinct",
            "top_values",
        ],
    )
    focus_df.to_parquet(config.CACHE_DIR / "focus_attrs.parquet", index=False)

    # --- нормализация: память ---
    storage_fmt = Counter()
    storage_examples = {
        k: []
        for k in [
            "число+ГБ(лат)",
            "число+ГБ(кир)",
            "число без единицы",
            "число+ТБ",
            "число+МБ",
            "текст/диапазон",
        ]
    }
    for v, c in storage_values.items():
        m = STORAGE_RE.search(v)
        if m:
            u = m.group(3).lower()
            if u in ("тб", "tb"):
                storage_fmt["число+ТБ"] += c
                key = "число+ТБ"
            elif u == "гб":
                key = "число+ГБ(кир)"
                storage_fmt[key] += c
            elif u == "gb":
                key = "число+ГБ(лат)"
                storage_fmt[key] += c
            elif u in ("мб", "mb"):
                storage_fmt["число+МБ"] += c
                key = "число+МБ"
            else:
                key = "текст/диапазон"
                storage_fmt[key] += c
        elif BARE_NUM_RE.match(v):
            storage_fmt["число без единицы"] += c
            key = "число без единицы"
        else:
            storage_fmt["текст/диапазон"] += c
            key = "текст/диапазон"
        if len(storage_examples[key]) < 8:
            storage_examples[key].append(v)
    storage_norm = {
        "total_values": int(sum(storage_values.values())),
        "distinct_values": int(len(storage_values)),
        "format_counts": dict(storage_fmt),
        "top_values": storage_values.most_common(20),
        "examples": storage_examples,
    }

    # --- нормализация: диагональ экрана ---
    diagonal_fmt = Counter()
    for v, c in diagonal_values.items():
        if DIAG_INCH_RE.search(v) or '"' in v or "”" in v:
            diagonal_fmt["дюймы"] += c
        elif DIAG_CM_RE.search(v):
            diagonal_fmt["сантиметры"] += c
        elif BARE_NUM_RE.match(v):
            diagonal_fmt["число без единицы"] += c
        else:
            diagonal_fmt["текст/диапазон"] += c
    diagonal_norm = {
        "total_values": int(sum(diagonal_values.values())),
        "distinct_values": int(len(diagonal_values)),
        "format_counts": dict(diagonal_fmt),
        "top_values": diagonal_values.most_common(20),
    }

    # --- нормализация: цвет ---
    norm_color_map: dict[str, Counter] = defaultdict(Counter)
    for v, c in color_values.items():
        norm_color_map[_norm_color(v)][v] += c
    color_collisions = {norm: dict(cnt) for norm, cnt in norm_color_map.items() if len(cnt) > 1}
    color_norm = {
        "total_values": int(sum(color_values.values())),
        "distinct_values": int(len(color_values)),
        "distinct_after_lower_norm": int(len(norm_color_map)),
        "collision_count": int(len(color_collisions)),
        "collisions_sample": dict(list(color_collisions.items())[:25]),
        "top_values": color_values.most_common(25),
    }

    loaders.save_json("catalog_summary.json", summary)
    loaders.save_json("storage_norm.json", storage_norm)
    loaders.save_json("diagonal_norm.json", diagonal_norm)
    loaders.save_json("color_norm.json", color_norm)
    return summary

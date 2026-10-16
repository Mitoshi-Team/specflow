"""Связи между источниками и «заземление» атрибутов в тексте карточек."""

from __future__ import annotations

import re

import pandas as pd

from . import config, loaders

WS_RE = re.compile(r"\s+")


def _norm(s: str) -> str:
    return WS_RE.sub(" ", str(s).strip().lower().replace("ё", "е"))


def _contains(text_norm: str, needle_norm: str) -> bool:
    needle_norm = needle_norm.strip()
    if len(needle_norm) < 2:
        return False
    return needle_norm in text_norm


def run() -> dict:
    offer_df, cat_df = loaders.build_catalog_tables()
    cards = loaders.load_cards(columns=["sku_id", "title", "description"])
    cards["sku_id"] = cards.sku_id.astype(str)
    offer_df["sku_id"] = offer_df.sku_id.astype(str)

    click_df = pd.read_parquet(config.CACHE_DIR / "clicks_skus.parquet")
    click_skus = set(click_df.sku_id.astype(str))

    s_cards = set(cards.sku_id)
    s_offers = set(offer_df.sku_id)

    overlap = {
        "n_cards": len(s_cards),
        "n_offers": len(s_offers),
        "n_click_skus": len(click_skus),
        "offers_cards": len(s_offers & s_cards),
        "offers_clicks": len(s_offers & click_skus),
        "cards_clicks": len(s_cards & click_skus),
        "all_three": len(s_offers & s_cards & click_skus),
        "offers_only": len(s_offers - s_cards - click_skus),
        "cards_only": len(s_cards - s_offers - click_skus),
        "clicks_only": len(click_skus - s_offers - s_cards),
    }

    # --- заземление vendor/model/color ---
    merged = offer_df.merge(cards, on="sku_id", how="inner")
    # цвет из параметров (один проход по pickle)
    raw = loaders.load_raw_offers()
    color_by_sku: dict[str, str] = {}
    for o in raw["yml_catalog"]["shop"]["offers"]["offer"]:
        params = o.get("param", [])
        for p in params:
            if isinstance(p, dict) and p.get("@name") in ("Цвет", "Цвет_search"):
                v = p.get("#text")
                if v:
                    color_by_sku[str(o["@id"])] = str(v)
                break
    merged["color"] = merged.sku_id.map(color_by_sku)

    merged["title_n"] = merged.title.map(_norm)
    merged["desc_n"] = merged.description.map(_norm)

    def ground(row, field):
        val = row[field]
        if pd.isna(val):
            return pd.Series(
                [False, False, False], index=[f"{field}_title", f"{field}_desc", f"{field}_any"]
            )
        nv = _norm(val)
        in_t = _contains(row["title_n"], nv)
        in_d = _contains(row["desc_n"], nv)
        return pd.Series(
            [in_t, in_d, in_t or in_d], index=[f"{field}_title", f"{field}_desc", f"{field}_any"]
        )

    for field in ["vendor", "model", "color"]:
        g = merged.apply(lambda r: ground(r, field), axis=1)
        merged = pd.concat([merged, g], axis=1)

    total = len(merged)
    grounding = {}
    for field in ["vendor", "model", "color"]:
        present = merged[field].notna()
        denom = int(present.sum())
        grounding[field] = {
            "n_with_value": denom,
            "title": float(merged.loc[present, f"{field}_title"].mean()) if denom else 0.0,
            "desc": float(merged.loc[present, f"{field}_desc"].mean()) if denom else 0.0,
            "any": float(merged.loc[present, f"{field}_any"].mean()) if denom else 0.0,
        }

    # примеры провалов заземления
    miss = merged[merged.model_any == False][["sku_id", "title", "model", "vendor"]].head(5)
    grounding_examples = miss.to_dict("records")

    # пометки о vendor: часто ли vendor в латинице
    vendor_latin = offer_df.vendor.fillna("").str.contains(r"[A-Za-z]").mean()

    summary = {
        "overlap": overlap,
        "grounding": grounding,
        "grounding_examples": grounding_examples,
        "vendor_latin_share": float(vendor_latin),
        "n_merge_cols": int(merged.shape[1]),
    }
    loaders.save_json("coverage_summary.json", summary)

    # сохраним матрицу для возможных графиков (размер небольшой)
    merged[["sku_id", "category_id", "vendor", "vendor_any", "model_any", "color_any"]].to_parquet(
        config.CACHE_DIR / "grounding.parquet", index=False
    )
    return summary

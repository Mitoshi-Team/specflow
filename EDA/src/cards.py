"""Анализ текстовых карточек (sku_desc.parquet)."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import config, loaders

HTML_TAG_RE = re.compile(r"<[a-zA-Z/][^>]*>")
HTML_ENTITY_RE = re.compile(r"&[a-zA-Z]+;|&#\d+;")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
MOJIBAKE_RE = re.compile(r"[ÃÂÐÑ][\x80-\xbf]")
REPLACEMENT_RE = re.compile("\ufffd")
DIGIT_RE = re.compile(r"\d")
LATIN_RE = re.compile(r"[A-Za-z]")
CYR_RE = re.compile(r"[А-Яа-яЁё]")


def _lang_class(title: pd.Series) -> pd.Series:
    lat = title.str.count(LATIN_RE)
    cyr = title.str.count(CYR_RE)
    out = np.where(
        (cyr > 0) & (lat > 0),
        "RU+EN",
        np.where(cyr > 0, "RU", np.where(lat > 0, "EN", "нет букв")),
    )
    return pd.Series(out, index=title.index)


def run() -> dict:
    df = loaders.load_cards(columns=["sku_id", "title", "description"])
    n = len(df)

    summary: dict = {"n_rows": int(n), "n_unique_sku": int(df.sku_id.nunique())}

    per_col: dict = {}
    for col in ["title", "description"]:
        s = df[col].fillna("")
        length = s.str.len()
        per_col[col] = {
            "n_missing": int(df[col].isna().sum()),
            "n_blank": int((s.str.strip() == "").sum()),
            "len_mean": float(length.mean()),
            "len_median": float(length.median()),
            "len_p95": float(length.quantile(0.95)),
            "len_p99": float(length.quantile(0.99)),
            "len_max": int(length.max()),
            "len_min": int(length.min()),
            "has_html_tag_share": float(s.str.contains(HTML_TAG_RE).mean()),
            "has_br_share": float(s.str.contains(r"<br\s*/?>", case=False, regex=True).mean()),
            "has_newline_share": float(s.str.contains("\n").mean()),
            "has_entity_share": float(s.str.contains(HTML_ENTITY_RE).mean()),
            "has_url_share": float(s.str.contains(URL_RE).mean()),
            "has_digit_share": float(s.str.contains(DIGIT_RE).mean()),
            "mojibake_share": float(s.str.contains(MOJIBAKE_RE).mean()),
            "replacement_char_share": float(s.str.contains(REPLACEMENT_RE).mean()),
        }
    summary["columns"] = per_col

    # дубликаты
    summary["dup_titles"] = int(df.title.duplicated().sum())
    summary["dup_descriptions"] = int(df.description.duplicated().sum())
    summary["dup_title_groups"] = int(df.title.duplicated().sum())

    # язык заголовков
    lang = _lang_class(df.title.fillna(""))
    summary["title_lang_mix"] = lang.value_counts().to_dict()

    # топ повторяющихся заголовков
    top_titles = df.title.value_counts().head(config.TOP_N)
    top_titles.to_frame("count").to_csv(config.RESULTS_DIR / "cards_top_titles.csv")

    # фрагменты-«шаблоны» в описаниях (частая реклама продавцов)
    filler = {
        "Лучшие товары из Китая": df.description.str.contains(
            "Лучшие товары из Китая", regex=False
        ).sum(),
        "Характеристики:": df.description.str.contains("Характеристики:", regex=False).sum(),
        "Комплектация:": df.description.str.contains("Комплектация", regex=False).sum(),
        "Описание:": df.description.str.contains("Описание:", regex=False).sum(),
    }
    summary["description_markers"] = {k: int(v) for k, v in filler.items()}

    # распределения длин (сэмпл для графиков)
    sample = pd.DataFrame(
        {
            "title_len": df.title.fillna("").str.len(),
            "desc_len": df.description.fillna("").str.len(),
        }
    )
    sample.to_parquet(config.CACHE_DIR / "cards_lengths.parquet", index=False)

    # примеры «грязных» описаний
    examples = {}
    examples["html"] = (
        df.description[df.description.str.contains(HTML_TAG_RE, na=False)].head(3).tolist()
    )
    examples["mojibake"] = (
        df.description[df.description.str.contains(MOJIBAKE_RE, na=False)].head(3).tolist()
    )
    examples["duplicate_title"] = top_titles.head(3).index.tolist()
    summary["examples"] = {k: [str(x)[:300] for x in v] for k, v in examples.items()}

    loaders.save_json("cards_summary.json", summary)
    return summary

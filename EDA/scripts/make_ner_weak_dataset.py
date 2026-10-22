"""Генерация weak-датасета для NER (distant supervision)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd


def norm_value(s: str) -> str:
    if not s:
        return s
    t = str(s).strip().lower()
    t = t.replace("ё", "е")
    # GB/ГБ нормализации
    t = t.replace("гигабайт", "гб").replace("гигабайта", "гб").replace("гб", "gb").replace("гбайт", "gb")
    t = t.replace("терабайт", "тб").replace("тб", "tb")
    t = t.replace("мегабайт", "мб").replace("мб", "mb")
    t = t.replace(",", ".")
    return " ".join(t.split())


def find_spans(text: str, value: str) -> list[tuple[int, int]]:
    if not text or not value:
        return []
    t = text.lower()
    v = norm_value(value)
    spans = []
    if v in t:
        start = t.find(v)
        end = start + len(v)
        spans.append((start, end))
    return spans


def main():
    base = Path("EDA/dataset")
    out_dir = Path("data/ner")
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "weak.jsonl"
    desc = pd.read_parquet(base / "sku_desc.parquet") if (base / "sku_desc.parquet").exists() else pd.DataFrame()
    df = desc.copy() if hasattr(desc, "copy") else pd.DataFrame()
    written = 0
    if df is None or (hasattr(df, "empty") and df.empty):
        print("empty df")
        return
    with out.open("w", encoding="utf-8") as f:
        for _, row in df.head(5000).iterrows():
            title = str(row.get("title", ""))
            desc_txt = str(row.get("description", ""))
            text = (title + "  " + desc_txt).strip()
            seller = row.get("seller_attributes") or row.get("sellerAttrs") or {}
            if not isinstance(seller, dict):
                seller = {}
            for char, prop in seller.items():
                spans = find_spans(text, str(prop))
                if spans:
                    ents = []
                    se, ee = spans[0]
                    ents.append({"start": se, "end": ee, "label": "PROPERTY"})
                    rec = {"text": text[:4000], "entities": ents, "char": char}
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    written += 1
                    if written % 500 == 0:
                        print(written)
    print("done", written)


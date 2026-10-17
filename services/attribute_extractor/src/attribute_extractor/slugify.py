"""Слагификация имён характеристик для генерации кодов новых полей."""

import re

from attribute_extractor.constants import SLUG_REPLACE


def slugify(name: str) -> str:
    if not name:
        return "field"
    s = name.strip().lower()
    for src, dst in SLUG_REPLACE.items():
        s = s.replace(src, dst)
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        return "field"
    return s

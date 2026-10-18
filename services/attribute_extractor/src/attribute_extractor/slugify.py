"""Слагификация имён характеристик для генерации кодов новых полей."""

import re

from attribute_extractor.constants import SLUG_REPLACE

_TRANSLIT = {
    **dict(
        zip(
            "абвгдеёзийклмнопрстуфхцчшщъыьэюя",
            (
                "a",
                "b",
                "v",
                "g",
                "d",
                "e",
                "z",
                "zh",
                "i",
                "y",
                "k",
                "l",
                "m",
                "n",
                "o",
                "p",
                "r",
                "s",
                "t",
                "u",
                "f",
                "kh",
                "ts",
                "ch",
                "sh",
                "shch",
                "",
                "y",
                "",
                "e",
                "yu",
                "ya",
            ),
            strict=True,
        )
    ),
    "ё": "e",
}


def slugify(name: str) -> str:
    if not name:
        return "field"
    s = name.strip().lower()
    s = "".join(_TRANSLIT.get(char, char) for char in s)
    for src, dst in SLUG_REPLACE.items():
        s = s.replace(src, dst)
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        return "field"
    return s

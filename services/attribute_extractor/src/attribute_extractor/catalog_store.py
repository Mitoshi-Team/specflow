"""Персистентность FieldCatalog и FieldBlocklist."""

import json
import os
from pathlib import Path

from attribute_extractor.constants import (
    DEFAULT_FIELD_BLOCKLIST_PATH,
    DEFAULT_FIELD_CATALOG_PATH,
)


class CatalogStore:
    """Атомарное сохранение/загрузка каталога полей и блоклиста."""

    def __init__(
        self,
        catalog_path: str | Path = DEFAULT_FIELD_CATALOG_PATH,
        blocklist_path: str | Path = DEFAULT_FIELD_BLOCKLIST_PATH,
    ) -> None:
        self.catalog_path = Path(catalog_path)
        self.blocklist_path = Path(blocklist_path)
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.blocklist_path.parent.mkdir(parents=True, exist_ok=True)

    def load_catalog(self) -> dict:
        try:
            if self.catalog_path.exists():
                with self.catalog_path.open(encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {"version": "1.0.0", "entries": []}

    def save_catalog(self, data: dict) -> None:
        tmp = self.catalog_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.catalog_path)

    def load_blocklist(self) -> list[str]:
        try:
            if self.blocklist_path.exists():
                with self.blocklist_path.open(encoding="utf-8") as f:
                    return [line.rstrip("\n\r") for line in f if line.strip()]
        except Exception:
            pass
        return []

    def save_blocklist(self, entries: list[str]) -> None:
        tmp = self.blocklist_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for e in entries:
                f.write(e + "\n")
        os.replace(tmp, self.blocklist_path)

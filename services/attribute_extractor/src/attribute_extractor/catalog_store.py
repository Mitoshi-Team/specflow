"""Персистентность FieldCatalog и FieldBlocklist."""

import json
import logging
import os
from pathlib import Path

from attribute_extractor.constants import (
    DEFAULT_FIELD_BLOCKLIST_PATH,
    DEFAULT_FIELD_CATALOG_PATH,
)
from attribute_extractor.field_catalog_seed import FIELD_CATALOG_VERSION

logger = logging.getLogger(__name__)


def _empty_catalog() -> dict:
    """Свежий пустой каталог (дефолт при отсутствии или сбое загрузки)."""
    return {"version": FIELD_CATALOG_VERSION, "entries": []}


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
        """Загрузить каталог полей.

        Отсутствие файла — штатный первый запуск, возвращается пустой каталог
        без лога. Битый/недоступный файл — деградация с ERROR-логом: сбой
        чтения не должен ронять сервис, но и не должен пройти молча (раньше
        широкий ``except: pass`` маскировал порчу данных, а последующее
        ``save_catalog`` затирало файл пустым каталогом).
        """
        if not self.catalog_path.exists():
            return _empty_catalog()
        try:
            with self.catalog_path.open(encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            logger.exception(
                "Не удалось загрузить каталог полей из %s; используется пустой каталог",
                self.catalog_path,
            )
            return _empty_catalog()
        if not isinstance(data, dict):
            logger.error(
                "Каталог полей в %s имеет неожиданную структуру (%s); используется пустой каталог",
                self.catalog_path,
                type(data).__name__,
            )
            return _empty_catalog()
        return data

    def save_catalog(self, data: dict) -> None:
        tmp = self.catalog_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.catalog_path)

    def load_blocklist(self) -> list[str]:
        """Загрузить блоклист; аналогично ``load_catalog`` — сбой читается в лог."""
        if not self.blocklist_path.exists():
            return []
        try:
            with self.blocklist_path.open(encoding="utf-8") as f:
                return [line.rstrip("\n\r") for line in f if line.strip()]
        except (OSError, UnicodeDecodeError):
            logger.exception(
                "Не удалось загрузить блоклист полей из %s; используется пустой блоклист",
                self.blocklist_path,
            )
            return []

    def save_blocklist(self, entries: list[str]) -> None:
        tmp = self.blocklist_path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for e in entries:
                f.write(e + "\n")
        os.replace(tmp, self.blocklist_path)

"""FieldCatalog, FieldBlocklist, FieldResolver (резолв характеристик в коды полей)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from attribute_extractor import slugify
from attribute_extractor.catalog_store import CatalogStore
from attribute_extractor.constants import (
    DEFAULT_FIELD_BLOCKLIST_PATH,
    DEFAULT_FIELD_CATALOG_PATH,
    DEFAULT_MATCH_THRESHOLD,
    DEFAULT_VECTOR_K,
)
from attribute_extractor.vector_index import LexicalVectorIndex, VectorIndex

logger = logging.getLogger(__name__)

FIELD_TEXT_SEPARATOR = " ; "
"""Разделитель имени поля и синонимов при сборке текста для индексации."""


@dataclass
class FieldCatalogEntry:
    code: str
    name_ru: str
    synonyms: list[str] = field(default_factory=list)
    value_type: str | None = None
    unit: str | None = None
    is_new_field: bool = False


@dataclass
class CharacteristicMatch:
    characteristic: str
    matched_code: str | None
    match_score: float
    is_new_field: bool
    blocked: bool


def _entry_text(entry: FieldCatalogEntry) -> str:
    """Текст поля для индексации: каноническое имя и все синонимы."""
    return FIELD_TEXT_SEPARATOR.join([entry.name_ru, *entry.synonyms])


class FieldBlocklist:
    def __init__(self, entries: list[str] | None = None) -> None:
        self._entries = {e.strip().lower() for e in (entries or []) if e.strip()}

    def add_entry(self, e: str) -> None:
        if e.strip():
            self._entries.add(e.strip().lower())

    def is_blocked(self, name: str) -> bool:
        if not name:
            return False
        n = name.strip().lower()
        return n in self._entries or any(e and e in n for e in self._entries)


class FieldCatalog:
    def __init__(self, entries: list[FieldCatalogEntry] | None = None) -> None:
        self._entries: dict[str, FieldCatalogEntry] = {}
        for e in entries or []:
            self._entries[e.code] = e

    @classmethod
    def from_store(cls, store: CatalogStore) -> FieldCatalog:
        """Загрузить каталог из персистентного хранилища (пустой, если нет данных)."""
        data = store.load_catalog()
        entries = [
            FieldCatalogEntry(
                code=item["code"],
                name_ru=item.get("name_ru", item["code"]),
                synonyms=list(item.get("synonyms") or []),
                value_type=item.get("value_type"),
                unit=item.get("unit"),
                is_new_field=bool(item.get("is_new_field", False)),
            )
            for item in data.get("entries", [])
            if item.get("code")
        ]
        return cls(entries)

    def all(self) -> list[FieldCatalogEntry]:
        return list(self._entries.values())

    def get(self, code: str) -> FieldCatalogEntry | None:
        return self._entries.get(code)

    def has(self, code: str) -> bool:
        return code in self._entries

    def add_new(self, entry: FieldCatalogEntry) -> None:
        if entry.code not in self._entries:
            self._entries[entry.code] = entry


class FieldResolver:
    def __init__(
        self,
        catalog: FieldCatalog | None = None,
        blocklist: FieldBlocklist | None = None,
        vector_index: VectorIndex | None = None,
        store: CatalogStore | None = None,
        match_threshold: float = DEFAULT_MATCH_THRESHOLD,
        vector_k: int = DEFAULT_VECTOR_K,
        persist_new_fields: bool = True,
    ) -> None:
        self.store = store or CatalogStore(DEFAULT_FIELD_CATALOG_PATH, DEFAULT_FIELD_BLOCKLIST_PATH)
        self.catalog = catalog if catalog is not None else FieldCatalog.from_store(self.store)
        self.blocklist = (
            blocklist if blocklist is not None else FieldBlocklist(self.store.load_blocklist())
        )
        self.vector_index = vector_index or LexicalVectorIndex()
        self.match_threshold = match_threshold
        self.vector_k = vector_k
        # Слабая разметка/пробы не должны дописывать боевой каталог: новые
        # поля живут только в памяти (domain-model.md: авто-добавление —
        # управляемое поведение, а не побочный эффект).
        self.persist_new_fields = persist_new_fields
        self._index_catalog()

    def _index_catalog(self) -> None:
        for entry in self.catalog.all():
            self.vector_index.add(entry.code, self.vector_index.embed(_entry_text(entry)))

    def resolve(self, characteristic: str) -> CharacteristicMatch:
        if not characteristic:
            return CharacteristicMatch(
                characteristic="",
                matched_code=None,
                match_score=0.0,
                is_new_field=False,
                blocked=False,
            )
        if self.blocklist.is_blocked(characteristic):
            return CharacteristicMatch(
                characteristic=characteristic,
                matched_code=None,
                match_score=0.0,
                is_new_field=False,
                blocked=True,
            )
        vec = self.vector_index.embed(characteristic)
        results = self.vector_index.search(vec, k=self.vector_k) if vec else []
        if results:
            best_code, best_score = results[0]
            if best_code and best_score >= self.match_threshold:
                # Поле, добавленное в память ранее как «новое», остаётся
                # новым и при повторных матчах: иначе потребители (weak
                # разметка, статистика) примут мусорный код за канонический.
                entry = self.catalog.get(best_code)
                return CharacteristicMatch(
                    characteristic=characteristic,
                    matched_code=best_code,
                    match_score=float(best_score),
                    is_new_field=bool(entry is not None and entry.is_new_field),
                    blocked=False,
                )
        code = slugify.slugify(characteristic)
        entry = FieldCatalogEntry(code=code, name_ru=characteristic, is_new_field=True)
        self.catalog.add_new(entry)
        self.vector_index.add(code, self.vector_index.embed(_entry_text(entry)))
        self._persist_new_field(code, characteristic)
        return CharacteristicMatch(
            characteristic=characteristic,
            matched_code=code,
            match_score=float(results[0][1]) if results else 0.0,
            is_new_field=True,
            blocked=False,
        )

    def _persist_new_field(self, code: str, characteristic: str) -> None:
        if not self.persist_new_fields:
            return
        try:
            data = self.store.load_catalog()
            entries = data.get("entries", [])
            if not any(e.get("code") == code for e in entries):
                entries.append({"code": code, "name_ru": characteristic, "is_new_field": True})
                data["entries"] = entries
                self.store.save_catalog(data)
        except Exception:  # noqa: BLE001 — персистентность best effort, отказ не должен ронять резолв
            # Сбой записи не должен прерывать разрешение карточки (новое поле
            # уже в памяти), но обязан фиксироваться с traceback: раньше поле
            # терялось молча при следующем рестарте.
            logger.exception(
                "Не удалось сохранить новое поле %s (%r) в каталог %s",
                code,
                characteristic,
                self.store.catalog_path,
            )

"""FieldCatalog, FieldBlocklist, FieldResolver (минимум для NER+эмбеддингов)."""

from __future__ import annotations

from dataclasses import dataclass

from attribute_extractor import slugify
from attribute_extractor.catalog_store import CatalogStore
from attribute_extractor.constants import (
    DEFAULT_FIELD_BLOCKLIST_PATH,
    DEFAULT_FIELD_CATALOG_PATH,
    DEFAULT_MATCH_THRESHOLD,
    DEFAULT_VECTOR_K,
)
from attribute_extractor.vector_index import InMemoryVectorIndex, LexicalVectorIndex


@dataclass
class FieldCatalogEntry:
    code: str
    name_ru: str
    synonyms: list[str] | None = None
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
        vector_index: InMemoryVectorIndex | LexicalVectorIndex | None = None,
        store: CatalogStore | None = None,
        match_threshold: float = DEFAULT_MATCH_THRESHOLD,
        vector_k: int = DEFAULT_VECTOR_K,
    ) -> None:
        self.catalog = catalog or FieldCatalog()
        self.blocklist = blocklist or FieldBlocklist()
        self.vector_index = vector_index or LexicalVectorIndex()
        self.store = store or CatalogStore(DEFAULT_FIELD_CATALOG_PATH, DEFAULT_FIELD_BLOCKLIST_PATH)
        self.match_threshold = match_threshold
        self.vector_k = vector_k
        for e in self.catalog.all():
            self.vector_index.add(e.code)

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
                return CharacteristicMatch(
                    characteristic=characteristic,
                    matched_code=best_code,
                    match_score=float(best_score),
                    is_new_field=False,
                    blocked=False,
                )
        code = slugify.slugify(characteristic)
        entry = FieldCatalogEntry(code=code, name_ru=characteristic, is_new_field=True)
        self.catalog.add_new(entry)
        self.vector_index.add(code)
        try:
            data = self.store.load_catalog()
            entries = data.get("entries", [])
            if not any(e.get("code") == code for e in entries):
                entries.append({"code": code, "name_ru": characteristic, "is_new_field": True})
                data["entries"] = entries
                self.store.save_catalog(data)
        except Exception:
            pass
        return CharacteristicMatch(
            characteristic=characteristic,
            matched_code=code,
            match_score=float(results[0][1]) if results else 0.0,
            is_new_field=True,
            blocked=False,
        )

"""Тесты резолва характеристик в коды полей."""

from __future__ import annotations

import logging

from attribute_extractor import fields, slugify, vector_index
from attribute_extractor.catalog_store import CatalogStore


def test_slugify_transliterates_cyrillic():
    assert slugify.slugify("Бренд смартфона") == "brend_smartfona"
    assert slugify.slugify("Пиковая частота видеокарты") == "pikovaya_chastota_videokarty"


def test_slugify_fallback_for_symbols_only():
    assert slugify.slugify("###") == "field"
    assert slugify.slugify("") == "field"


def _store(tmp_path, entries=None, blocklist=None) -> CatalogStore:
    store = CatalogStore(tmp_path / "cat.json", tmp_path / "bl.txt")
    if entries is not None:
        store.save_catalog({"version": "1.0.0", "entries": entries})
    if blocklist is not None:
        store.save_blocklist(blocklist)
    return store


def test_field_resolver_new_field_when_below_threshold(tmp_path):
    vi = vector_index.LexicalVectorIndex()
    vi.add("color")
    r = fields.FieldResolver(
        vector_index=vi,
        match_threshold=0.9,
        store=_store(tmp_path),
    )
    m = r.resolve("объём памяти")
    assert m.is_new_field is True
    assert m.matched_code is not None


def test_field_resolver_repeated_new_field_stays_new(tmp_path):
    """Повторный матч по полю, добавленному в память, не превращает его в канон."""
    vi = vector_index.LexicalVectorIndex()
    vi.add("color")
    r = fields.FieldResolver(
        vector_index=vi,
        match_threshold=0.9,
        store=_store(tmp_path),
    )
    first = r.resolve("Разрешение по вертикали")
    second = r.resolve("Разрешение по вертикали")
    assert first.is_new_field is True
    assert second.is_new_field is True
    assert second.matched_code == first.matched_code


def test_field_resolver_blocklist(tmp_path):
    r = fields.FieldResolver(
        blocklist=fields.FieldBlocklist(["запчасть"]),
        store=_store(tmp_path),
    )
    m = r.resolve("Запчасть")
    assert m.blocked is True


def test_field_resolver_matches_synonym_to_canonical_code(tmp_path):
    store = _store(
        tmp_path,
        entries=[
            {
                "code": "ram",
                "name_ru": "Оперативная память",
                "synonyms": ["ОЗУ", "RAM"],
                "is_new_field": False,
            },
            {
                "code": "color",
                "name_ru": "Цвет",
                "synonyms": ["Цвет корпуса"],
                "is_new_field": False,
            },
        ],
    )
    r = fields.FieldResolver(store=store)
    m = r.resolve("ОЗУ")
    assert m.matched_code == "ram"
    assert m.is_new_field is False
    assert m.match_score >= r.match_threshold


def test_field_resolver_matches_name_despite_synonyms(tmp_path):
    store = _store(
        tmp_path,
        entries=[
            {
                "code": "ram",
                "name_ru": "Оперативная память",
                "synonyms": ["ОЗУ", "RAM"],
                "is_new_field": False,
            }
        ],
    )
    r = fields.FieldResolver(store=store)
    m = r.resolve("оперативная память")
    assert m.matched_code == "ram"


def test_field_resolver_loads_blocklist_from_store(tmp_path):
    store = _store(tmp_path, blocklist=["продавец"])
    r = fields.FieldResolver(store=store)
    m = r.resolve("Продавец")
    assert m.blocked is True


def test_field_catalog_from_store_reads_synonyms(tmp_path):
    store = _store(
        tmp_path,
        entries=[
            {
                "code": "ram",
                "name_ru": "Оперативная память",
                "synonyms": ["ОЗУ"],
                "is_new_field": False,
            }
        ],
    )
    catalog = fields.FieldCatalog.from_store(store)
    entry = catalog.get("ram")
    assert entry is not None
    assert entry.synonyms == ["ОЗУ"]


def test_persist_new_field_failure_logs_and_keeps_match(tmp_path, monkeypatch, caplog):
    """Сбой записи нового поля не роняет резолв, но виден в логе (регрессия к
    хакатон-ревью: раньше ``except Exception: pass`` терял поле молча)."""
    store = _store(tmp_path)

    def _failing_save(data):
        raise OSError("диск недоступен")

    monkeypatch.setattr(store, "save_catalog", _failing_save)
    r = fields.FieldResolver(store=store)
    with caplog.at_level(logging.ERROR, logger="attribute_extractor.fields"):
        m = r.resolve("объём памяти")
    assert m.is_new_field is True
    assert any("obem_pamyati" in record.getMessage() for record in caplog.records)


def test_field_resolver_survives_corrupt_catalog_file(tmp_path):
    """Битый файл каталога деградирует пустым каталогом, резолв не падает."""
    store = _store(tmp_path)
    store.catalog_path.write_text("{битый json", encoding="utf-8")
    r = fields.FieldResolver(store=store)
    assert r.catalog.all() == []


def test_persist_new_fields_accumulate_after_repeated_load(tmp_path):
    """Кэш персиста: каждое авто-добавление догоняет файл целиком.

    Регрессия к O(N²): при N авто-добавлениях файл перечитывался и
    перепарсивался N раз; при сбое записи очередное поле не терялось при
    следующей успешной записи.
    """
    import json

    store = _store(tmp_path)
    r = fields.FieldResolver(store=store)
    first = r.resolve("объём памяти")
    second = r.resolve("цвет бампера")
    assert first.is_new_field and second.is_new_field

    data = json.loads(store.catalog_path.read_text(encoding="utf-8"))
    codes = [entry["code"] for entry in data["entries"]]
    assert codes == ["obem_pamyati", "tsvet_bampera"]

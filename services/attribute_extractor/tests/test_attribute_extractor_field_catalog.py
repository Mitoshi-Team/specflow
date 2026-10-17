"""Тесты сборки каталога полей и блоклиста из seed."""

from __future__ import annotations

from attribute_extractor import catalog_builder
from attribute_extractor.field_catalog_seed import CANONICAL_FIELDS, FIELD_CATALOG_VERSION

EXPECTED_CODES = {
    "brand",
    "model",
    "color",
    "storage",
    "ram",
    "diagonal",
    "battery_capacity",
    "drive",
    "processor",
}


def test_build_catalog_has_nine_canonical_fields() -> None:
    catalog = catalog_builder.build_catalog()
    codes = {entry["code"] for entry in catalog["entries"]}
    assert codes == EXPECTED_CODES
    assert catalog["version"] == FIELD_CATALOG_VERSION


def test_build_catalog_entries_carry_name_and_synonyms() -> None:
    catalog = catalog_builder.build_catalog()
    ram = next(entry for entry in catalog["entries"] if entry["code"] == "ram")
    assert ram["name_ru"] == "Оперативная память"
    assert "ОЗУ" in ram["synonyms"]
    assert ram["is_new_field"] is False


def test_build_is_deterministic() -> None:
    first_catalog, first_blocklist = catalog_builder.build()
    second_catalog, second_blocklist = catalog_builder.build()
    assert first_catalog == second_catalog
    assert first_blocklist == second_blocklist


def test_seed_has_no_duplicate_codes() -> None:
    codes = [seed.code for seed in CANONICAL_FIELDS]
    assert len(codes) == len(set(codes))


def test_enrich_catalog_appends_observed_name_as_synonym() -> None:
    catalog = catalog_builder.build_catalog()
    param_stats = [("Оперативная память DDR4", 100), ("Случайный шум", 100)]
    catalog_builder.enrich_catalog(catalog, param_stats, min_count=20)
    ram = next(entry for entry in catalog["entries"] if entry["code"] == "ram")
    assert "Оперативная память DDR4" in ram["synonyms"]
    assert "Случайный шум" not in ram["synonyms"]


def test_enrich_catalog_skips_below_min_count() -> None:
    catalog = catalog_builder.build_catalog()
    param_stats = [("Оперативная память DDR4", 5)]
    catalog_builder.enrich_catalog(catalog, param_stats, min_count=20)
    ram = next(entry for entry in catalog["entries"] if entry["code"] == "ram")
    assert "Оперативная память DDR4" not in ram["synonyms"]


def test_enrich_catalog_requires_whole_word_match() -> None:
    catalog = catalog_builder.build_catalog()
    param_stats = [
        ("Диагональное расположение отверстий", 100),
        ("Максимальная диагональ экрана", 100),
    ]
    catalog_builder.enrich_catalog(catalog, param_stats, min_count=20)
    diagonal = next(entry for entry in catalog["entries"] if entry["code"] == "diagonal")
    assert "Максимальная диагональ экрана" in diagonal["synonyms"]
    assert "Диагональное расположение отверстий" not in diagonal["synonyms"]


def test_collect_blocklist_picks_noise_names() -> None:
    param_stats = [("Продавец", 500), ("Цвет", 400)]
    extra = catalog_builder.collect_blocklist(param_stats, min_count=20)
    assert "Продавец" in extra
    assert "Цвет" not in extra


def test_build_blocklist_includes_seed_entries() -> None:
    blocklist = catalog_builder.build_blocklist()
    assert "продавец" in blocklist

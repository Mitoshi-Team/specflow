"""Реестр схем категорий: сборка артефакта и загрузка (задача 1.3).

Сборщик тестируется на парquet-фикстурах (EDA/cache-структура без внешних
сервисов): required/optional по fill rate, порог min_cards, отбрасывание
шумовых/неканонических имён, персист каталога полей и text-only инвариант.
Загрузчик (``SchemaRegistry.from_file``) — roundtrip, битые входы, fallback.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from attribute_extractor.catalog_store import CatalogStore
from attribute_extractor.category_schema_builder import CANONICAL_CODES, build, save
from attribute_extractor.constants import (
    CATEGORY_SCHEMA_MIN_CARDS,
    CATEGORY_SCHEMA_REQUIRED_SHARE,
    CATEGORY_SCHEMA_VERSION,
)
from attribute_extractor.preprocessing import SchemaRegistry
from specflow_contracts import AttributeValueType, ProductCard

# --- Фикстуры EDA/cache -------------------------------------------------------


def _write_parquet(path: Path, columns: dict[str, list]) -> Path:
    pd.DataFrame(columns).to_parquet(path, index=False)
    return path


@pytest.fixture()
def eda_cache(tmp_path: Path) -> dict[str, Path]:
    """Каталог с таблицами EDA/cache: 4 категории, 55 карточек, 8 параметров."""
    category_ids = ["1", "2", "3", "4"]
    categories = _write_parquet(
        tmp_path / "categories.parquet",
        {
            "category_id": category_ids,
            "category_name": ["Смартфоны", "Ноутбуки", "Книги", "Редкая категория"],
        },
    )

    offers_rows: dict[str, list] = {"category_id": [], "vendor": [], "model": []}
    for index in range(20):  # Смартфоны: vendor 16/20 (0.8), model 6/20 (0.3)
        offers_rows["category_id"].append("1")
        offers_rows["vendor"].append("Realme" if index < 16 else "")
        offers_rows["model"].append("C33" if index < 6 else "")
    for _ in range(10):  # Ноутбуки: vendor/model 10/10 (1.0)
        offers_rows["category_id"].append("2")
        offers_rows["vendor"].append("Lenovo")
        offers_rows["model"].append("IdeaPad")
    for _ in range(20):  # Книги: vendor/model не заполнены вовсе
        offers_rows["category_id"].append("3")
        offers_rows["vendor"].append("")
        offers_rows["model"].append("")
    for _ in range(5):  # Редкая: меньше min_cards
        offers_rows["category_id"].append("4")
        offers_rows["vendor"].append("Издательство")
        offers_rows["model"].append("")
    offers = _write_parquet(tmp_path / "offers_flat.parquet", offers_rows)

    cat_attr = _write_parquet(
        tmp_path / "cat_attr.parquet",
        {
            "category_id": ["1", "1", "1", "2", "2", "2", "3", "4"],
            "param": [
                "Цвет",
                "Встроенная память",
                "Процессор",
                "Оперативная память",
                "Подборки",
                "Мега-характеристика",
                "Материал",
                "Цвет",
            ],
            "fill_rate": [0.9, 0.6, 0.3, 0.45, 0.9, 0.8, 0.9, 1.0],
        },
    )
    param_stats = _write_parquet(
        tmp_path / "param_stats.parquet",
        {
            "param": [
                "Цвет",
                "Оперативная память",
                "Встроенная память",
                "Процессор",
                "Подборки",
                "Материал",
                "Мега-характеристика",
            ],
            "n": [100, 90, 80, 70, 50, 40, 30],
        },
    )
    return {
        "categories": categories,
        "offers": offers,
        "cat_attr": cat_attr,
        "param_stats": param_stats,
    }


def _build(eda_cache: dict[str, Path], **overrides) -> dict:
    return build(
        categories_path=eda_cache["categories"],
        offers_path=eda_cache["offers"],
        cat_attr_path=eda_cache["cat_attr"],
        param_stats_path=eda_cache["param_stats"],
        **overrides,
    )


def _codes(attributes: list[dict]) -> list[str]:
    return [attribute["code"] for attribute in attributes]


# --- Сборщик ------------------------------------------------------------------


def test_build_splits_required_and_optional_by_share(eda_cache) -> None:
    payload = _build(eda_cache)

    assert payload["version"] == CATEGORY_SCHEMA_VERSION
    schemas = {schema["category"]: schema for schema in payload["schemas"]}
    assert set(schemas) == {"Смартфоны", "Ноутбуки"}

    smartphones = schemas["Смартфоны"]
    assert smartphones["category_id"] == "1"
    assert smartphones["schema_version"] == CATEGORY_SCHEMA_VERSION
    # fill rate >= 0.5 → обязательные; 0 < share < 0.5 → опциональные.
    assert _codes(smartphones["required_attributes"]) == ["brand", "color", "storage"]
    assert _codes(smartphones["optional_attributes"]) == ["model", "processor"]
    storage = next(item for item in smartphones["required_attributes"] if item["code"] == "storage")
    assert storage["value_type"] == AttributeValueType.UNIT_VALUE
    assert storage["unit"] == "ГБ"
    assert storage["is_required"] is True
    color = next(item for item in smartphones["required_attributes"] if item["code"] == "color")
    assert color["value_type"] == AttributeValueType.ENUM


def test_build_takes_brand_model_from_offer_columns(eda_cache) -> None:
    """brand/model считаются по колонкам vendor/model, а не только cat_attr."""
    payload = _build(eda_cache)
    laptops = next(schema for schema in payload["schemas"] if schema["category"] == "Ноутбуки")

    # vendor/model заполнены в 10/10 карточках Ноутбуков → обязательные.
    assert _codes(laptops["required_attributes"]) == ["brand", "model"]
    # ram из cat_attr с долей 0.45 → опциональный.
    assert _codes(laptops["optional_attributes"]) == ["ram"]


def test_build_skips_small_and_fieldless_categories(eda_cache) -> None:
    """Категории без канонических полей и меньше min_cards в реестр не входят."""
    payload = _build(eda_cache)
    names = [schema["category"] for schema in payload["schemas"]]

    # Редкая категория: 5 карточек < CATEGORY_SCHEMA_MIN_CARDS.
    # Книги: единственный параметр («Материал») неканонический → схема пуста.
    assert "Редкая категория" not in names
    assert "Книги" not in names


def test_build_ignores_blocked_and_noncanonical_params(eda_cache) -> None:
    """Блоклист, авто-добавляемые и неканонические имена не дают кодов."""
    payload = _build(eda_cache)

    used = {
        attribute["code"]
        for schema in payload["schemas"]
        for attribute in schema["required_attributes"] + schema["optional_attributes"]
    }
    # «Подборки» (блоклист), «Материал» и «Мега-характеристика» (auto-add)
    # из cat_attr не дали ни одного кода — только канонические поля.
    assert used <= CANONICAL_CODES


def test_build_does_not_persist_field_catalog(eda_cache, monkeypatch) -> None:
    """Офлайн-сборка не пишет каталог полей в data/ (только временный каталог)."""
    recorded: list[Path] = []
    original = CatalogStore.save_catalog

    def spy(self, data) -> None:
        recorded.append(Path(self.catalog_path).resolve())
        original(self, data)

    monkeypatch.setattr(CatalogStore, "save_catalog", spy)
    _build(eda_cache)

    repo_data = Path(__file__).resolve().parents[3] / "data"
    assert all(not path.is_relative_to(repo_data.resolve()) for path in recorded)


def test_build_is_text_only(eda_cache) -> None:
    """В схему не попадают vocab/значения seller-атрибутов (инвариант text-only)."""
    payload = _build(eda_cache)

    for schema in payload["schemas"]:
        assert set(schema) == {
            "category",
            "schema_version",
            "category_id",
            "required_attributes",
            "optional_attributes",
        }
        for attribute in schema["required_attributes"] + schema["optional_attributes"]:
            assert attribute["vocab"] is None
            assert attribute["normalization_rules"] is None
            assert attribute["category_scope"] is None


def test_build_thresholds_are_configurable(eda_cache) -> None:
    """Пороги required_share/min_cards переопределяются через API build."""
    strict = _build(eda_cache, required_share=0.9)
    smartphones = next(schema for schema in strict["schemas"] if schema["category"] == "Смартфоны")
    # 0.6 и 0.8 < 0.9 → storage/brand становятся опциональными, color (0.9) остаётся.
    assert _codes(smartphones["required_attributes"]) == ["color"]
    assert _codes(smartphones["optional_attributes"]) == ["brand", "model", "storage", "processor"]

    larger = _build(eda_cache, min_cards=20)
    names = [schema["category"] for schema in larger["schemas"]]
    # Ноутбуки (10 карточек) отсеиваются, Смартфоны (20) остаются.
    assert names == ["Смартфоны"]
    # Дефолты зафиксированы в constants.py (не инлайновые числа в логике).
    assert (CATEGORY_SCHEMA_REQUIRED_SHARE, CATEGORY_SCHEMA_MIN_CARDS) == (0.5, 10)


def test_build_is_deterministic(eda_cache) -> None:
    """Повторная сборка на тех же данных даёт идентичный артефакт."""
    assert _build(eda_cache) == _build(eda_cache)


# --- Загрузчик ----------------------------------------------------------------


def test_save_and_from_file_roundtrip(eda_cache, tmp_path: Path) -> None:
    payload = _build(eda_cache)
    artifact = tmp_path / "category_schemas.json"
    save(payload, artifact)

    registry = SchemaRegistry.from_file(artifact)
    assert len(registry.all()) == 2
    by_name = registry.get(category_name="смартфоны")
    assert by_name is not None and by_name.category_id == "1"
    by_id = registry.get(category_id="2")
    assert by_id is not None and by_id.category == "Ноутбуки"
    assert registry.get(category_name="Книги") is None
    # Карточка неизвестной категории → generic-fallback, а не None.
    resolved = registry.resolve(ProductCard(title="товар", category_name="Книги"))
    assert resolved.category == "generic"
    # all() возвращает копию: внешняя мутация не ломает реестр.
    registry.all().clear()
    assert len(registry.all()) == 2


def test_save_is_atomic_and_creates_parents(eda_cache, tmp_path: Path) -> None:
    artifact = tmp_path / "nested" / "category_schemas.json"
    save(_build(eda_cache), artifact)

    assert artifact.exists()
    assert not artifact.with_suffix(".tmp").exists()


def test_from_file_missing_artifact_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        SchemaRegistry.from_file(tmp_path / "absent.json")


def test_from_file_invalid_shape_raises(tmp_path: Path) -> None:
    for content in ("[]", '{"schemas": {}}'):
        artifact = tmp_path / "bad.json"
        artifact.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError, match="Некорректный формат"):
            SchemaRegistry.from_file(artifact)


def test_from_file_corrupt_json_raises(tmp_path: Path) -> None:
    artifact = tmp_path / "corrupt.json"
    artifact.write_text("{не json", encoding="utf-8")
    with pytest.raises(ValueError):
        SchemaRegistry.from_file(artifact)


def test_from_file_invalid_schema_item_raises(tmp_path: Path) -> None:
    artifact = tmp_path / "bad_item.json"
    artifact.write_text(
        json.dumps({"version": "1.0.0", "schemas": [{"category": 42}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        SchemaRegistry.from_file(artifact)

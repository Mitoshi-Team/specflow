"""Тесты слабой разметки NER (weak_markup.py) на синтетических данных."""

from __future__ import annotations

from attribute_extractor import weak_markup
from attribute_extractor.catalog_store import CatalogStore
from attribute_extractor.fields import FieldResolver


def _resolver(tmp_path) -> FieldResolver:
    store = CatalogStore(tmp_path / "cat.json", tmp_path / "bl.txt")
    store.save_catalog(
        {
            "version": "1.0.0",
            "entries": [
                {"code": code, "name_ru": name}
                for code, name in (
                    ("brand", "Бренд"),
                    ("ram", "Оперативная память"),
                    ("storage", "Встроенная память"),
                    ("color", "Цвет"),
                )
            ],
        }
    )
    return FieldResolver(store=store)


def test_find_value_span_exact_and_normalization(tmp_path) -> None:
    text = "Заголовок: Смартфон X 128GB Black"
    # «128 ГБ» находит «128GB» (канонизация единиц), регистр не важен.
    span = weak_markup.find_value_span(text, "128 ГБ")
    assert span is not None
    start, end = span
    assert text[start:end] == "128GB"
    span = weak_markup.find_value_span(text, "black")
    assert span is not None
    assert text[span[0] : span[1]] == "Black"


def test_find_value_span_short_single_token_rejected() -> None:
    assert weak_markup.find_value_span("Заголовок: X 5", "5") is None


def test_build_record_pairs_characteristic_and_property(tmp_path) -> None:
    resolver = _resolver(tmp_path)
    record = weak_markup.build_record(
        "Смартфон Acme X 8/256 ГБ черный",
        "Оперативная память 8 ГБ, встроенная память 256 ГБ, цвет черный.",
        [{"name": "Оперативная память", "value": "8 ГБ"}, {"name": "Цвет", "value": "черный"}],
        resolver,
        sku_id="s1",
        category_name="Смартфоны",
    )
    assert record is not None
    by_label = {
        span.label: [s for s in record.spans if s.label == span.label] for span in record.spans
    }
    assert any(span.attribute_code == "ram" for span in by_label["PROPERTY"])
    assert any(span.attribute_code == "color" for span in by_label["PROPERTY"])
    assert any(span.attribute_code == "ram" for span in by_label["CHARACTERISTIC"])
    for span in record.spans:
        assert record.text[span.start : span.end] == span.text
    assert record.as_dict()["spans"] == [span.as_dict() for span in record.spans]


def test_build_record_skips_unresolved_parameter_and_missing_value(tmp_path) -> None:
    resolver = _resolver(tmp_path)
    record = weak_markup.build_record(
        "Заголовок: Ноутбук Acme",
        "Гарантия предоставляется.",
        [
            {"name": "Гарантия", "value": "1 год"},  # поле вне каталога
            {"name": "RAM", "value": "16 ГБ"},  # значения нет в тексте
            {"name": "Цвет", "value": "да"},  # тривиальное значение
        ],
        resolver,
    )
    assert record is None


def test_build_record_uses_section_labels(tmp_path) -> None:
    resolver = _resolver(tmp_path)
    record = weak_markup.build_record(
        "Смартфон Acme X", "", [{"name": "Цвет", "value": "черный"}], resolver
    )
    if record is not None:
        assert "Заголовок:" in record.text


def test_parse_seller_params_mapping_and_yml_forms() -> None:
    mapping = weak_markup.parse_seller_params({"Цвет": "черный", "RAM": "8 ГБ"})
    assert mapping == [{"name": "Цвет", "value": "черный"}, {"name": "RAM", "value": "8 ГБ"}]
    yml = weak_markup.parse_seller_params([{"@name": "Цвет", "@value": "черный"}])
    assert yml == [{"name": "Цвет", "value": "черный"}]
    assert weak_markup.parse_seller_params(None) == []


def test_stratified_split_is_deterministic_and_stratified(tmp_path) -> None:
    resolver = _resolver(tmp_path)
    records = [
        weak_markup.build_record(
            f"Смартфон Acme X{i} 8 ГБ",
            "",
            [{"name": "Оперативная память", "value": "8 ГБ"}],
            resolver,
            sku_id=f"s{i}",
            category_name="Ноутбуки" if i % 2 else "Смартфоны",
        )
        for i in range(20)
    ]
    train, val = weak_markup.stratified_split([r for r in records if r], val_share=0.2)
    assert len(val) == 4
    assert len(train) == 16
    train_ids = {r.sku_id for r in train}
    val_ids = {r.sku_id for r in val}
    assert not train_ids & val_ids
    again_train, again_val = weak_markup.stratified_split([r for r in records if r], val_share=0.2)
    assert {r.sku_id for r in again_val} == val_ids

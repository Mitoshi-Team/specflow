"""Тесты сэмплирования и валидации gold-набора (gold_sampling.py)."""

from __future__ import annotations

import json
from pathlib import Path

from attribute_extractor.gold_sampling import (
    GOLD_CATEGORY_QUOTAS,
    GOLD_SAMPLE_SIZE,
    GOLD_SEED,
    grounding_errors,
    is_usable,
    parse_offer_params,
    select_diverse,
    validate_gold,
)

GOLD_PATH = Path(__file__).resolve().parents[1] / "gold" / "gold.jsonl"


def make_card(
    sku_id: str,
    *,
    category_id: str = "cat-1",
    category_name: str = "Смартфоны",
    vendor: str = "Vendor",
    title: str = "Смартфон X",
    description: str = "Описание товара с полезными характеристиками",
    seller_attributes: dict[str, str] | None = None,
) -> dict:
    return {
        "sku_id": sku_id,
        "category_id": category_id,
        "category_name": category_name,
        "vendor": vendor,
        "title": title,
        "description": description,
        "seller_attributes": seller_attributes if seller_attributes is not None else {},
    }


def make_record(
    sku_id: str,
    expected: list[dict] | None = None,
    *,
    card: dict | None = None,
) -> dict:
    return {
        "card": card
        if card is not None
        else make_card(sku_id, title="Смартфон Samsung Galaxy 8/256 ГБ"),
        "expected": expected
        if expected is not None
        else [{"attribute_code": "brand", "normalized_value": "Samsung"}],
        "notes": None,
    }


class TestParseOfferParams:
    def test_parses_single_and_list_params(self):
        offer = {
            "param": [
                {"@name": "Бренд", "#text": "Samsung"},
                {"@name": "Память", "#text": "256 ГБ"},
            ]
        }
        assert parse_offer_params(offer) == {"Бренд": "Samsung", "Память": "256 ГБ"}

    def test_skips_entries_without_name_or_value(self):
        offer = {"param": [{"#text": "x"}, {"@name": "Цвет"}, {"@name": " ", "#text": "y"}, "junk"]}
        assert parse_offer_params(offer) == {}

    def test_missing_param_key(self):
        assert parse_offer_params({}) == {}


class TestIsUsable:
    def test_card_without_text_is_not_usable(self):
        assert not is_usable(make_card("s1", title="", description=""))

    def test_long_description_is_usable(self):
        assert is_usable(make_card("s1", title="", description="о" * 40))

    def test_many_seller_attributes_are_usable_despite_short_description(self):
        card = make_card(
            "s1", title="T", description="коротко", seller_attributes={"a": "1", "b": "2", "c": "3"}
        )
        assert is_usable(card)

    def test_thin_card_is_not_usable(self):
        card = make_card("s1", title="T", description="коротко", seller_attributes={"a": "1"})
        assert not is_usable(card)


class TestSelectDiverse:
    def test_deterministic_for_same_seed(self):
        cards = [make_card(f"s{i}") for i in range(30)]
        first = [c["sku_id"] for c in select_diverse(cards, 10, seed=GOLD_SEED)]
        second = [c["sku_id"] for c in select_diverse(cards, 10, seed=GOLD_SEED)]
        assert first == second

    def test_returns_requested_count_from_large_pool(self):
        cards = [
            make_card(f"s{i}", category_id=f"cat-{i % 4}", vendor=f"v{i % 8}") for i in range(100)
        ]
        assert len(select_diverse(cards, 20, seed=1)) == 20

    def test_respects_category_limit_when_alternatives_exist(self):
        cards = []
        for category in ("cat-a", "cat-b"):
            for i in range(15):
                cards.append(make_card(f"{category}-{i}", category_id=category, vendor=f"v{i}"))
        selected = select_diverse(cards, 6, seed=1, max_per_category=3)
        by_category = [card["category_id"] for card in selected]
        assert by_category.count("cat-a") == 3
        assert by_category.count("cat-b") == 3
        assert len(selected) == 6

    def test_respects_vendor_limit(self):
        cards = [make_card(f"s{i}", vendor="OnlyVendor") for i in range(10)]
        selected = select_diverse(cards, 10, seed=1, max_per_vendor=4)
        assert len(selected) == 4

    def test_falls_back_without_limits_when_caps_block_progress(self):
        cards = [make_card(f"s{i}", vendor=f"v{i}") for i in range(6)]
        selected = select_diverse(cards, 6, seed=1, max_per_vendor=1)
        assert len(selected) == 6

    def test_covers_categories_when_count_allows(self):
        cards = (
            [make_card(f"a{i}", category_id="cat-a") for i in range(5)]
            + [make_card(f"b{i}", category_id="cat-b") for i in range(5)]
            + [make_card(f"c{i}", category_id="cat-c") for i in range(5)]
        )
        selected = select_diverse(cards, 3, seed=7)
        assert {card["category_id"] for card in selected} == {"cat-a", "cat-b", "cat-c"}

    def test_pool_smaller_than_count(self):
        cards = [make_card("s1"), make_card("s2")]
        selected = select_diverse(cards, 10, seed=1)
        assert {card["sku_id"] for card in selected} == {"s1", "s2"}

    def test_empty_pool(self):
        assert select_diverse([], 10, seed=1) == []

    def test_quotas_fill_strata(self):
        cards = [
            make_card(f"p{i}", category_id="cat-p", category_name="Смартфоны", vendor=f"v{i}")
            for i in range(10)
        ] + [
            make_card(f"l{i}", category_id="cat-l", category_name="Ноутбуки", vendor=f"w{i}")
            for i in range(10)
        ]
        selected = select_diverse(cards, 5, seed=1, quotas={"Смартфоны": 3, "Ноутбуки": 2})
        names = [card["category_name"] for card in selected]
        assert names.count("Смартфоны") == 3
        assert names.count("Ноутбуки") == 2

    def test_quota_shortage_is_filled_from_other_categories(self):
        cards = [
            make_card("p1", category_id="cat-p", category_name="Смартфоны"),
            make_card("t1", category_id="cat-t", category_name="Телевизоры"),
            make_card("t2", category_id="cat-t", category_name="Телевизоры"),
            make_card("t3", category_id="cat-t", category_name="Телевизоры"),
        ]
        selected = select_diverse(cards, 3, seed=1, quotas={"Смартфоны": 50})
        names = [card["category_name"] for card in selected]
        assert names.count("Смартфоны") == 1
        assert len(selected) == 3

    def test_quotas_are_deterministic(self):
        cards = [
            make_card(f"s{i}", category_id=f"cat-{i % 3}", category_name=f"К{i % 3}")
            for i in range(30)
        ]
        quotas = {"К0": 2, "К1": 2}
        first = [c["sku_id"] for c in select_diverse(cards, 6, seed=5, quotas=quotas)]
        second = [c["sku_id"] for c in select_diverse(cards, 6, seed=5, quotas=quotas)]
        assert first == second


class TestValidateGold:
    def test_valid_records(self):
        assert validate_gold([make_record("s1")]) == []

    def test_empty_list(self):
        assert validate_gold([]) == []

    def test_missing_sku(self):
        record = make_record("s1")
        record["card"]["sku_id"] = ""
        errors = validate_gold([record])
        assert any("нет sku_id" in error for error in errors)

    def test_duplicate_sku(self):
        errors = validate_gold([make_record("s1"), make_record("s1")])
        assert any("дубликат sku_id" in error for error in errors)

    def test_empty_expected(self):
        errors = validate_gold([make_record("s1", expected=[])])
        assert any("expected пуст" in error for error in errors)

    def test_unknown_attribute_code(self):
        record = make_record(
            "s1", expected=[{"attribute_code": "unknown", "normalized_value": "x"}]
        )
        errors = validate_gold([record])
        assert any("неизвестный код" in error for error in errors)

    def test_duplicate_attribute_code(self):
        expected = [
            {"attribute_code": "brand", "normalized_value": "Samsung"},
            {"attribute_code": "brand", "normalized_value": "Apple"},
        ]
        errors = validate_gold([make_record("s1", expected=expected)])
        assert any("дубликат кода" in error for error in errors)

    def test_empty_value(self):
        record = make_record("s1", expected=[{"attribute_code": "brand", "normalized_value": " "}])
        errors = validate_gold([record])
        assert any("пустое значение" in error for error in errors)

    def test_expected_not_a_list(self):
        record = make_record("s1")
        record["expected"] = "brand"
        errors = validate_gold([record])
        assert any("expected пуст" in error for error in errors)


class TestGroundingErrors:
    def test_grounded_values_pass(self):
        record = make_record("s1")
        assert grounding_errors([record]) == []

    def test_value_absent_from_text_is_reported(self):
        record = make_record(
            "s1",
            expected=[{"attribute_code": "brand", "normalized_value": "Apple"}],
            card=make_card("s1", title="Смартфон Samsung", description="", seller_attributes={}),
        )
        errors = grounding_errors([record])
        assert len(errors) == 1
        assert "brand" in errors[0]

    def test_color_yo_folds_to_ye(self):
        card = make_card("s1", title="Смартфон Чёрный корпус", description="")
        record = make_record(
            "s1",
            expected=[{"attribute_code": "color", "normalized_value": "черный"}],
            card=card,
        )
        assert grounding_errors([record]) == []

    def test_decimal_comma_and_inch_alias(self):
        card = make_card("s1", title='Смартфон 6,7" OLED', description="")
        record = make_record(
            "s1",
            expected=[{"attribute_code": "diagonal", "normalized_value": "6.7 дюйм"}],
            card=card,
        )
        assert grounding_errors([record]) == []

    def test_seller_attributes_field_is_searchable(self):
        card = make_card(
            "s1",
            title="Смартфон",
            description="",
            seller_attributes={"Ёмкость аккумулятора": "5000 мА·ч"},
        )
        record = make_record(
            "s1",
            expected=[{"attribute_code": "battery_capacity", "normalized_value": "5000 мА·ч"}],
            card=card,
        )
        assert grounding_errors([record]) == []


def load_gold() -> list[dict]:
    return [
        json.loads(line)
        for line in GOLD_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class TestGoldDataset:
    def test_size_and_quota_distribution(self):
        records = load_gold()
        assert len(records) == GOLD_SAMPLE_SIZE
        counts: dict[str, int] = {}
        for record in records:
            name = record["card"]["category_name"]
            counts[name] = counts.get(name, 0) + 1
        assert counts == GOLD_CATEGORY_QUOTAS

    def test_structure_is_valid(self):
        assert validate_gold(load_gold()) == []

    def test_all_values_are_grounded(self):
        assert grounding_errors(load_gold()) == []

    def test_annotated_records_have_notes(self):
        assert all(record.get("notes") for record in load_gold())

    def test_expected_covers_key_fields(self):
        expected_codes = {
            item["attribute_code"] for record in load_gold() for item in record["expected"]
        }
        assert {"brand", "model", "color", "storage", "ram", "diagonal"} <= expected_codes

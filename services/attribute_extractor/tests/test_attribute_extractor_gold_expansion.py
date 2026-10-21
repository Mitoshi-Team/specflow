"""Тесты расширения gold-набора: curated-карточки, hard set, слияние наборов.

Проверяется целостность расширения (``gold/gold_expansion.jsonl``,
``gold/hard_set.jsonl``) и его согласованность с корпусным сэмплом
(``gold/gold.jsonl``): размеры, квоты категорий, подтверждение значений
текстом карточки, отсутствие пересечения ``sku_id``.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from attribute_extractor.constants import (
    GOLD_EXPANSION_SIZE,
    GOLD_HARD_SET_MAX_SIZE,
    GOLD_HARD_SET_MIN_SIZE,
    GOLD_HARD_SET_SIZE,
    GOLD_MIN_RECORDS,
    GOLD_SOURCE_CORPUS,
    GOLD_SOURCE_CURATED,
    GOLD_TAG_HARD,
)
from attribute_extractor.gold_sampling import (
    GOLD_EXPANSION_QUOTAS,
    existing_sku_ids,
    gold_source,
    grounding_errors,
    hard_set_records,
    is_hard_case,
    merge_gold_records,
    select_expansion,
    validate_gold,
    validate_hard_set,
)

_SERVICE_DIR = Path(__file__).resolve().parents[1]
GOLD_DIR = _SERVICE_DIR / "gold"
GOLD_PATH = GOLD_DIR / "gold.jsonl"
EXPANSION_PATH = GOLD_DIR / "gold_expansion.jsonl"
HARD_SET_PATH = GOLD_DIR / "hard_set.jsonl"
CURATED_CARDS_PATH = GOLD_DIR / "curated_cards.json"


def _load_script(name: str):
    script = _SERVICE_DIR / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class TestCuratedCardsSource:
    def test_card_count_matches_expansion_size(self):
        payload = json.loads(CURATED_CARDS_PATH.read_text(encoding="utf-8"))
        assert len(payload["cards"]) == GOLD_EXPANSION_SIZE

    def test_category_quotas_match(self):
        payload = json.loads(CURATED_CARDS_PATH.read_text(encoding="utf-8"))
        counts: dict[str, int] = {}
        for card in payload["cards"]:
            name = str(card["category_name"])
            counts[name] = counts.get(name, 0) + 1
        assert counts == GOLD_EXPANSION_QUOTAS

    def test_sku_ids_are_unique(self):
        payload = json.loads(CURATED_CARDS_PATH.read_text(encoding="utf-8"))
        sku_ids = [str(card["sku_id"]) for card in payload["cards"]]
        assert len(sku_ids) == len(set(sku_ids))

    def test_every_card_has_text_and_expected(self):
        payload = json.loads(CURATED_CARDS_PATH.read_text(encoding="utf-8"))
        for card in payload["cards"]:
            assert (card["title"] or card["description"]).strip()
            assert card["expected"]

    def test_seller_attributes_are_not_part_of_expected(self):
        payload = json.loads(CURATED_CARDS_PATH.read_text(encoding="utf-8"))
        for card in payload["cards"]:
            codes = set(card["expected"])
            assert "seller_attributes" not in codes


class TestExpansionDataset:
    def test_size_and_quota_distribution(self):
        records = _load_jsonl(EXPANSION_PATH)
        assert len(records) == GOLD_EXPANSION_SIZE
        counts: dict[str, int] = {}
        for record in records:
            name = record["card"]["category_name"]
            counts[name] = counts.get(name, 0) + 1
        assert counts == GOLD_EXPANSION_QUOTAS

    def test_structure_is_valid(self):
        assert validate_gold(_load_jsonl(EXPANSION_PATH)) == []

    def test_all_values_are_grounded(self):
        assert grounding_errors(_load_jsonl(EXPANSION_PATH)) == []

    def test_records_are_marked_as_curated(self):
        records = _load_jsonl(EXPANSION_PATH)
        assert all(gold_source(record) == GOLD_SOURCE_CURATED for record in records)

    def test_hard_records_document_the_decision(self):
        records = _load_jsonl(EXPANSION_PATH)
        hard = hard_set_records(records)
        assert all(str(record.get("notes") or "").strip() for record in hard)

    def test_does_not_overlap_base_gold(self):
        base = existing_sku_ids(_load_jsonl(GOLD_PATH))
        expansion = existing_sku_ids(_load_jsonl(EXPANSION_PATH))
        assert not base & expansion

    def test_total_gold_size_reaches_minimum(self):
        total = len(_load_jsonl(GOLD_PATH)) + len(_load_jsonl(EXPANSION_PATH))
        assert total >= GOLD_MIN_RECORDS


class TestHardSet:
    def test_size_is_in_allowed_range(self):
        records = _load_jsonl(HARD_SET_PATH)
        assert GOLD_HARD_SET_MIN_SIZE <= len(records) <= GOLD_HARD_SET_MAX_SIZE
        assert len(records) == GOLD_HARD_SET_SIZE

    def test_structure_is_valid(self):
        assert validate_hard_set(_load_jsonl(HARD_SET_PATH)) == []

    def test_every_record_is_tagged_hard(self):
        assert all(is_hard_case(record) for record in _load_jsonl(HARD_SET_PATH))

    def test_hard_set_is_subset_of_expansion(self):
        expansion = existing_sku_ids(_load_jsonl(EXPANSION_PATH))
        hard = existing_sku_ids(_load_jsonl(HARD_SET_PATH))
        assert hard <= expansion

    def test_hard_set_records_are_grounded(self):
        assert grounding_errors(_load_jsonl(HARD_SET_PATH)) == []

    def test_hard_set_records_have_difficulty_tag(self):
        records = _load_jsonl(HARD_SET_PATH)
        assert all(
            len({str(tag) for tag in record["tags"]} - {GOLD_TAG_HARD}) > 0 for record in records
        )


class TestGoldSourceAndHardDetection:
    def test_default_source_is_corpus(self):
        assert gold_source({"card": {"sku_id": "s1"}}) == GOLD_SOURCE_CORPUS

    def test_explicit_source_is_kept(self):
        assert gold_source({"source": GOLD_SOURCE_CURATED}) == GOLD_SOURCE_CURATED

    def test_is_hard_case_requires_tag(self):
        assert not is_hard_case({"tags": []})
        assert not is_hard_case({"tags": ["range-value"]})
        assert is_hard_case({"tags": [GOLD_TAG_HARD, "range-value"]})
        assert not is_hard_case({})

    def test_hard_set_records_selects_tagged(self):
        records = [
            {"card": {"sku_id": "s1"}, "tags": [GOLD_TAG_HARD]},
            {"card": {"sku_id": "s2"}, "tags": ["range-value"]},
        ]
        assert [r["card"]["sku_id"] for r in hard_set_records(records)] == ["s1"]


class TestMergeAndSelection:
    def test_merge_keeps_first_record_for_duplicate_sku(self):
        base = [
            {
                "card": {"sku_id": "s1"},
                "expected": [{"attribute_code": "brand", "normalized_value": "A"}],
            }
        ]
        extra = [
            {
                "card": {"sku_id": "s1"},
                "expected": [{"attribute_code": "brand", "normalized_value": "B"}],
            }
        ]
        merged = merge_gold_records(base, extra)
        assert len(merged) == 1
        assert merged[0]["expected"][0]["normalized_value"] == "A"

    def test_merge_appends_new_records(self):
        base = [{"card": {"sku_id": "s1"}}]
        extra = [{"card": {"sku_id": "s2"}}]
        assert len(merge_gold_records(base, extra)) == 2

    def test_select_expansion_excludes_used_skus(self):
        cards = [{"sku_id": f"s{i}", "category_name": "Смартфоны"} for i in range(10)]
        selected = select_expansion(cards, 5, exclude_skus={"s0", "s1"})
        assert "s0" not in {card["sku_id"] for card in selected}
        assert "s1" not in {card["sku_id"] for card in selected}

    def test_select_expansion_is_sorted_and_deterministic(self):
        cards = [{"sku_id": f"s{i}", "category_name": "Смартфоны"} for i in range(10)]
        first = select_expansion(cards, 5)
        second = select_expansion(cards, 5)
        assert first == second
        assert [card["sku_id"] for card in first] == sorted(card["sku_id"] for card in first)

    def test_select_expansion_respects_quotas(self):
        cards = [
            {"sku_id": f"p{i}", "category_name": "Смартфоны", "vendor": f"vp{i}"} for i in range(20)
        ] + [
            {"sku_id": f"l{i}", "category_name": "Ноутбуки", "vendor": f"vl{i}"} for i in range(20)
        ]
        selected = select_expansion(
            cards, 10, quotas={"Смартфоны": 6, "Ноутбуки": 4}
        )
        names = [card["category_name"] for card in selected]
        assert names.count("Смартфоны") == 6
        assert names.count("Ноутбуки") == 4


class TestBuildCuratedScript:
    def test_check_mode_passes_for_repository_data(self):
        build = _load_script("build_gold_curated")
        assert build.main(["--check"]) == 0

    def test_build_record_uses_compact_expected_dict(self):
        build = _load_script("build_gold_curated")
        card = {
            "sku_id": "cur-test",
            "category_id": "761",
            "category_name": "Смартфоны",
            "title": "Смартфон Samsung",
            "description": "",
            "expected": {"brand": "Samsung"},
            "notes": "n",
            "tags": ["hard"],
        }
        record = build.build_record(card)
        assert record["expected"] == [{"attribute_code": "brand", "normalized_value": "Samsung"}]
        assert record["source"] == GOLD_SOURCE_CURATED
        assert record["tags"] == ["hard"]

    def test_seller_attributes_are_reported_when_absent_in_text(self):
        build = _load_script("build_gold_curated")
        card = {
            "sku_id": "cur-test",
            "title": "Смартфон Samsung",
            "description": "",
            "seller_attributes": {"Цвет": "зелёный"},
        }
        assert build.ungrounded_seller_values(card) == ["Цвет=зелёный"]


class TestEvaluateWithExpansion:
    def test_gold_extra_merges_and_splits_by_source(self, tmp_path: Path):
        evaluate = _load_script("evaluate")
        base = tmp_path / "gold.jsonl"
        extra = tmp_path / "gold_expansion.jsonl"
        metrics = tmp_path / "metrics.json"

        def record(sku_id: str, brand: str, source: str) -> dict:
            return {
                "card": {
                    "sku_id": sku_id,
                    "title": f"Смартфон {brand}",
                    "description": "",
                    "category_id": "761",
                    "category_name": "Смартфоны",
                },
                "expected": [{"attribute_code": "brand", "normalized_value": brand}],
                "notes": "n",
                "source": source,
                "tags": [],
            }

        base.write_text(
            json.dumps(record("p1", "Samsung", GOLD_SOURCE_CORPUS), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        extra.write_text(
            json.dumps(record("p2", "Apple", GOLD_SOURCE_CURATED), ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        exit_code = evaluate.main(
            [
                "--gold",
                str(base),
                "--gold-extra",
                str(extra),
                "--out",
                str(metrics),
            ]
        )
        assert exit_code == 0
        report = json.loads(metrics.read_text(encoding="utf-8"))
        assert report["products"] == 2
        assert set(report["by_source"]) == {GOLD_SOURCE_CORPUS, GOLD_SOURCE_CURATED}
        assert report["by_source"][GOLD_SOURCE_CURATED]["products"] == 1

    def test_duplicate_sku_across_gold_files_is_counted_once(self, tmp_path: Path):
        evaluate = _load_script("evaluate")
        base = tmp_path / "gold.jsonl"
        extra = tmp_path / "gold_expansion.jsonl"
        metrics = tmp_path / "metrics.json"
        record = {
            "card": {
                "sku_id": "p1",
                "title": "Смартфон Samsung",
                "description": "",
                "category_id": "761",
                "category_name": "Смартфоны",
            },
            "expected": [{"attribute_code": "brand", "normalized_value": "Samsung"}],
            "notes": "n",
        }
        base.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
        extra.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
        args = ["--gold", str(base), "--gold-extra", str(extra), "--out", str(metrics)]
        assert evaluate.main(args) == 0
        report = json.loads(metrics.read_text(encoding="utf-8"))
        assert report["products"] == 1

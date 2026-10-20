"""Метрики ``scripts/evaluate.py`` (задача 3) на синтетических данных.

Контрольные значения P/R/F1 считаются руками; внешние сервисы не
используются, артефакты пишутся во временный каталог.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from specflow_contracts import (
    AttributeCandidate,
    ExtractionMethod,
    ExtractionResult,
    ExtractionStatus,
)

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "evaluate.py"
_spec = importlib.util.spec_from_file_location("evaluate", _SCRIPT)
assert _spec is not None and _spec.loader is not None
evaluate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(evaluate)


def _result(product_id: str, attributes: list[tuple[str, str, float]]) -> ExtractionResult:
    return ExtractionResult(
        attributes=[
            AttributeCandidate(
                attribute_code=code,
                raw_value=value,
                normalized_value=value,
                confidence=confidence,
                extraction_method=ExtractionMethod.RULE,
                is_confirmed_in_text=True,
            )
            for code, value, confidence in attributes
        ],
        status=ExtractionStatus.OK,
        needs_review=False,
        pipeline_version="test",
        product_id=product_id,
    )


def _dump_results(results: list[ExtractionResult], path: Path) -> None:
    path.write_text(
        "\n".join(result.model_dump_json() for result in results) + "\n",
        encoding="utf-8",
    )


def _write_gold(path: Path) -> None:
    records = [
        {
            "card": {
                "sku_id": "p1",
                "title": "iPhone 128 ГБ",
                "description": "",
                "category_id": "761",
                "category_name": "Смартфоны",
            },
            "expected": [
                {"attribute_code": "brand", "normalized_value": "Apple"},
                {"attribute_code": "storage", "normalized_value": "128 ГБ"},
            ],
            "notes": "n1",
        },
        {
            "card": {
                "sku_id": "p2",
                "title": "Наушники Sony",
                "description": "",
                "category_id": "762",
                "category_name": "Наушники",
            },
            "expected": [{"attribute_code": "brand", "normalized_value": "Sony"}],
            "notes": "n2",
        },
    ]
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )


def test_compute_counts_and_prf() -> None:
    gold = {"p1": {"brand": {"Apple"}, "storage": {"128 ГБ"}}, "p2": {"brand": {"Sony"}}}
    preds = {"p1": {"brand": {"Apple"}, "storage": {"256 ГБ"}, "color": {"черный"}}}
    counts = evaluate.compute_counts(gold, preds)
    assert counts["brand"] == (1, 0, 1)  # TP Apple, FN Sony
    assert counts["storage"] == (0, 1, 1)  # FP 256, FN 128
    assert counts["color"] == (0, 1, 0)
    metrics = evaluate.attribute_metrics(counts)
    assert metrics["brand"]["precision"] == 1.0
    assert metrics["brand"]["recall"] == 0.5
    assert metrics["brand"]["f1"] == 2 * 1.0 * 0.5 / 1.5
    assert metrics["storage"]["precision"] == 0.0
    assert metrics["storage"]["f1"] == 0.0
    micro = evaluate._micro_average(counts)
    assert micro == {
        "precision": 1 / 3,
        "recall": 1 / 3,
        "f1": 1 / 3,
        "tp": 1,
        "fp": 2,
        "fn": 2,
    }


def test_macro_average_and_coverage() -> None:
    gold = {"p1": {"brand": {"Apple"}, "storage": {"128 ГБ"}}, "p2": {"brand": {"Sony"}}}
    preds = {"p1": {"brand": {"Apple"}, "storage": {"256 ГБ"}, "color": {"черный"}}}
    counts = evaluate.compute_counts(gold, preds)
    metrics = evaluate.attribute_metrics(counts)
    macro = evaluate._macro_average(metrics)
    assert macro["precision"] == (1.0 + 0.0 + 0.0) / 3
    coverage = evaluate.coverage_metrics(gold, preds)
    assert coverage["brand"] == 0.5
    assert coverage["storage"] == 0.5
    assert coverage["color"] == 0.5


def test_category_breakdown_splits_by_gold_category() -> None:
    records = [
        {
            "card": {
                "sku_id": "p1",
                "title": "t",
                "description": "",
                "category_id": "761",
                "category_name": "Смартфоны",
            },
            "expected": [{"attribute_code": "brand", "normalized_value": "Apple"}],
            "notes": "",
        },
        {
            "card": {
                "sku_id": "p2",
                "title": "t",
                "description": "",
                "category_id": "762",
                "category_name": "Наушники",
            },
            "expected": [{"attribute_code": "brand", "normalized_value": "Sony"}],
            "notes": "",
        },
    ]
    preds = [
        _result("p1", [("brand", "Apple", 0.9)]),
        _result("p2", []),
    ]
    gold = evaluate.build_gold_map(records)
    pred_map = evaluate.build_pred_map([r.model_dump() for r in preds])
    breakdown = evaluate.category_breakdown(records, gold, pred_map)
    assert breakdown["Смартфоны"]["brand"]["precision"] == 1.0
    assert breakdown["Наушники"]["brand"]["recall"] == 0.0


def test_below_threshold_shares() -> None:
    results = [
        _result("p1", [("brand", "Apple", 0.9), ("color", "черный", 0.5)]),
    ]
    shares = evaluate.below_threshold_shares([r.model_dump() for r in results])
    assert shares[str(0.8)] == 0.5
    assert shares[str(0.7)] == 0.5
    assert shares[str(0.9)] == 0.5


def test_main_with_predictions_file(tmp_path: Path) -> None:
    gold = tmp_path / "gold.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    metrics = tmp_path / "metrics.json"
    _write_gold(gold)
    _dump_results(
        [
            _result("p1", [("brand", "Apple", 0.9), ("storage", "256 ГБ", 0.9)]),
            _result("p2", [("brand", "Sony", 0.9)]),
        ],
        predictions,
    )
    exit_code = evaluate.main(
        ["--gold", str(gold), "--predictions", str(predictions), "--out", str(metrics)]
    )
    assert exit_code == 0
    report = json.loads(metrics.read_text(encoding="utf-8"))
    assert report["products"] == 2
    assert report["per_attribute"]["brand"]["tp"] == 2
    assert report["micro"]["f1"] > 0.0


def test_main_rerun_mode_missing_predictions(tmp_path: Path) -> None:
    gold = tmp_path / "gold.jsonl"
    metrics = tmp_path / "metrics.json"
    _write_gold(gold)
    exit_code = evaluate.main(["--gold", str(gold), "--out", str(metrics)])
    assert exit_code == 0
    report = json.loads(metrics.read_text(encoding="utf-8"))
    assert report["products"] == 2
    assert "grounding" not in report


def test_collect_errors_lists_fp_and_fn() -> None:
    records = [
        {
            "card": {
                "sku_id": "p1",
                "title": "t",
                "description": "",
                "category_id": "761",
                "category_name": "Смартфоны",
            },
            "expected": [{"attribute_code": "brand", "normalized_value": "Apple"}],
            "notes": "",
        }
    ]
    results = [_result("p1", [("brand", "Samsung", 0.9), ("color", "черный", 0.9)])]
    errors = evaluate.collect_errors(records, [r.model_dump() for r in results])
    fp = [entry for entry in errors if entry["kind"] == "fp"]
    fn = [entry for entry in errors if entry["kind"] == "fn"]
    assert [(e["attribute_code"], e["predicted"]) for e in fp] == [
        ("brand", "Samsung"),
        ("color", "черный"),
    ]
    assert fp[0]["expected"] == ["Apple"]
    assert [(e["attribute_code"], e["expected"]) for e in fn] == [("brand", "Apple")]
    assert fn[0]["predicted"] == ["Samsung"]
    assert {e["category"] for e in errors} == {"Смартфоны"}


def test_main_writes_errors_file(tmp_path: Path) -> None:
    gold = tmp_path / "gold.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    errors_path = tmp_path / "errors.jsonl"
    _write_gold(gold)
    _dump_results(
        [
            _result("p1", [("brand", "Apple", 0.9), ("storage", "256 ГБ", 0.9)]),
            _result("p2", []),
        ],
        predictions,
    )
    exit_code = evaluate.main(
        [
            "--gold",
            str(gold),
            "--predictions",
            str(predictions),
            "--errors",
            str(errors_path),
        ]
    )
    assert exit_code == 0
    errors = [json.loads(line) for line in errors_path.read_text(encoding="utf-8").splitlines()]
    kinds = {entry["kind"] for entry in errors}
    assert kinds == {"fp", "fn"}


def test_main_missing_gold_fails(tmp_path: Path) -> None:
    exit_code = evaluate.main(["--gold", str(tmp_path / "absent.jsonl")])
    assert exit_code == 1


def test_new_field_share_counts_new_field_candidates() -> None:
    """Доля кандидатов с is_new_field — метрика дрейфа каталога (§8)."""
    results = [
        {"attributes": [{"is_new_field": True}, {"is_new_field": False}]},
        {"attributes": []},
        {"attributes": [{"is_new_field": False}, {"is_new_field": False}]},
    ]
    assert evaluate.new_field_share(results) == 0.25
    assert evaluate.new_field_share([]) == 0.0


def test_build_report_includes_new_field_share() -> None:
    report = evaluate.build_report([], [])
    assert report["new_field_share"] == 0.0

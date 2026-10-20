"""Офлайн-прогон ``scripts/run_batch.py`` (задача 2).

Проверяется на синтетическом CSV во временном каталоге: битый JSON в
``seller_attributes`` даёт ``status=error`` и не прерывает поток; артефакты
пишутся строго в переданный каталог. Внешние сервисы не используются.
"""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

from specflow_contracts import ExtractionResult

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_batch.py"
_spec = importlib.util.spec_from_file_location("run_batch", _SCRIPT)
assert _spec is not None and _spec.loader is not None
run_batch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_batch)

# Карточка с детерминированными rule-кандидатами (confidence=0.9).
CLEAN_TITLE = "Смартфон realme C33 4/128GB Gold"


def _write_csv(directory: Path) -> Path:
    """Три строки: две корректные и одна с битым JSON в seller_attributes."""
    source = directory / "cards.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "product_id",
                "title",
                "description",
                "seller_attributes",
                "category_id",
                "category_name",
            ]
        )
        writer.writerow(["p1", CLEAN_TITLE, "", "", "761", "Смартфоны"])
        writer.writerow(
            [
                "p2",
                "Наушники Xiaomi Redmi Buds 4 Active",
                "",
                '{"Цвет": "чёрный"}',
                "762",
                "Наушники",
            ]
        )
        writer.writerow(["p3", "Экран 6.7 дюйма", "", "{битый json", "763", "Мониторы"])
    return source


def _read_jsonl(path: Path) -> list[ExtractionResult]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ExtractionResult.model_validate_json(line) for line in lines]


def test_run_batch_writes_valid_predictions(tmp_path: Path) -> None:
    """predictions.jsonl содержит валидные ExtractionResult; битая → error."""
    source = _write_csv(tmp_path)

    outcome = run_batch.run_offline(source, tmp_path)

    results = _read_jsonl(tmp_path / "predictions.jsonl")
    assert [result.product_id for result in results] == ["p1", "p2", "p3"]
    assert results[0].attributes, "по realme-карточке ожидаются rule-кандидаты"
    assert results[0].status.value in {"ok", "low_confidence", "partial"}
    assert results[2].status.value == "error"
    assert outcome["total"] == 3
    assert outcome["errors"] == 1


def test_run_batch_csv_matches_prediction_row_format(tmp_path: Path) -> None:
    """CSV-выгрузка соответствует PredictionRow (domain-model.md, 3.7)."""
    source = _write_csv(tmp_path)

    run_batch.run_offline(source, tmp_path, write_csv=True)

    with (tmp_path / "predictions.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    header = list(rows[0])
    assert header[:5] == ["product_id", "title", "category", "needs_review", "status"]
    assert "brand" in header and "brand_confidence" in header
    assert [row["product_id"] for row in rows] == ["p1", "p2", "p3"]
    assert rows[0]["title"] == CLEAN_TITLE
    assert rows[0]["category"] == "Смартфоны"
    assert rows[0]["brand"] == "realme"
    assert rows[2]["status"] == "error"


def test_run_batch_writes_only_to_output_dir(tmp_path: Path) -> None:
    """Запись строго в переданный каталог, а не рядом со скриптом/в репозиторий."""
    source = _write_csv(tmp_path)

    run_batch.run_offline(source, tmp_path, write_csv=True)

    written = {path.name for path in tmp_path.iterdir() if path.is_file() and path != source}
    assert written == {"predictions.jsonl", "predictions.csv", "needs_review.csv"}


def test_run_batch_limits_input_and_batches(tmp_path: Path) -> None:
    """--max-items урезает вход; --batch-size разбивает поток на части."""
    source = _write_csv(tmp_path)

    outcome = run_batch.run_offline(source, tmp_path, batch_size=2, max_items=2)

    results = _read_jsonl(tmp_path / "predictions.jsonl")
    assert len(results) == 2
    assert outcome["total"] == 2


def test_run_batch_accepts_gold_jsonl_format(tmp_path: Path) -> None:
    """JSONL с gold-обёрткой {\"card\": {\"sku_id\": ...}} разбирается напрямую."""
    source = tmp_path / "gold_like.jsonl"
    record = {
        "card": {
            "sku_id": "sku-1",
            "title": CLEAN_TITLE,
            "description": "",
            "category_id": "761",
            "category_name": "Смартфоны",
        }
    }
    source.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")

    run_batch.run_offline(source, tmp_path)

    result = _read_jsonl(tmp_path / "predictions.jsonl")[0]
    assert result.product_id == "sku-1"
    assert result.attributes


def test_run_batch_accepts_json_array(tmp_path: Path) -> None:
    """Файл .json в виде JSON-массива карточек принимается."""
    source = tmp_path / "cards.json"
    source.write_text(
        json.dumps([{"product_id": "a1", "title": CLEAN_TITLE}], ensure_ascii=False),
        encoding="utf-8",
    )

    run_batch.run_offline(source, tmp_path)

    results = _read_jsonl(tmp_path / "predictions.jsonl")
    assert len(results) == 1
    assert results[0].product_id == "a1"


def test_run_batch_rejects_invalid_input(tmp_path: Path) -> None:
    """Пустой файл и неподдерживаемое расширение → exit code 1, без traceback."""
    empty = tmp_path / "empty.csv"
    empty.touch()
    unsupported = tmp_path / "cards.xlsx"
    unsupported.write_text("x", encoding="utf-8")

    assert run_batch.main([str(empty), "--out", str(tmp_path)]) == 1
    assert run_batch.main([str(unsupported), "--out", str(tmp_path)]) == 1


def test_run_batch_rejects_invalid_batch_size(tmp_path: Path) -> None:
    """--batch-size вне 1..50 → ошибка аргументов (argparse)."""
    source = _write_csv(tmp_path)

    with pytest.raises(SystemExit):
        run_batch.main([str(source), "--out", str(tmp_path), "--batch-size", "0"])


def _review_result(
    attributes: list,
    status,
    needs_review: bool = True,
    product_id: str = "p1",
):
    return ExtractionResult(
        attributes=attributes,
        status=status,
        needs_review=needs_review,
        pipeline_version="test",
        product_id=product_id,
        category_name="Смартфоны",
        low_confidence_count=0,
        processing_time_ms=1,
    )


def _new_field_candidate():
    from attribute_extractor.constants import NER_CHARACTERISTIC_FEATURE_KEY
    from specflow_contracts import AttributeCandidate, ExtractionMethod

    return AttributeCandidate(
        attribute_code="matritsa",
        raw_value="IPS",
        normalized_value="IPS",
        confidence=0.95,
        extraction_method=ExtractionMethod.NER,
        is_confirmed_in_text=True,
        evidence_text="IPS",
        ner_score=0.95,
        is_new_field=True,
        features={NER_CHARACTERISTIC_FEATURE_KEY: "Матрица"},
    )


def _read_review_csv(directory: Path) -> list[dict[str, str]]:
    with (directory / "needs_review.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_review_csv_candidate_rows_by_reason(tmp_path: Path) -> None:
    """Кандидат пишется по строке на причину; карточки без ревью не пишутся."""
    from attribute_extractor.constants import AUTO_THRESHOLD, CONFLICT_FEATURE_KEY
    from specflow_contracts import AttributeCandidate, ExtractionMethod, ExtractionStatus

    conflict = AttributeCandidate(
        attribute_code="color",
        raw_value="черный",
        normalized_value="черный",
        confidence=0.95,
        extraction_method=ExtractionMethod.NER,
        is_confirmed_in_text=True,
        features={CONFLICT_FEATURE_KEY: True},
    )
    low = AttributeCandidate(
        attribute_code="brand",
        raw_value="Acme",
        normalized_value="Acme",
        confidence=AUTO_THRESHOLD - 0.1,
        extraction_method=ExtractionMethod.RULE,
        is_confirmed_in_text=True,
    )
    predictions = [
        (
            None,
            _review_result(
                [_new_field_candidate(), conflict, low], ExtractionStatus.LOW_CONFIDENCE
            ),
        ),
        (None, _review_result([], ExtractionStatus.SKIPPED, product_id="p2")),
        (None, _review_result([], ExtractionStatus.OK, needs_review=False, product_id="p3")),
    ]

    run_batch._write_review_csv(predictions, tmp_path / "needs_review.csv")

    rows = _read_review_csv(tmp_path)
    by_product_reason = [(row["product_id"], row["reason"]) for row in rows]
    assert ("p1", "new_field") in by_product_reason
    assert ("p1", "conflict") in by_product_reason
    assert ("p1", "low_confidence") in by_product_reason
    assert ("p2", "skipped") in by_product_reason
    assert all(row["product_id"] != "p3" for row in rows)

    new_field_row = next(row for row in rows if row["reason"] == "new_field")
    assert new_field_row["attribute_code"] == "matritsa"
    assert new_field_row["characteristic"] == "Матрица"
    assert new_field_row["is_new_field"] == "True"
    assert new_field_row["extraction_method"] == "ner"
    assert new_field_row["decision"] == ""


def test_review_csv_card_level_reasons(tmp_path: Path) -> None:
    """partial/error дают карточную строку с пустыми значениями."""
    from specflow_contracts import ExtractionStatus

    predictions = [
        (None, _review_result([], ExtractionStatus.PARTIAL, product_id="p4")),
        (None, _review_result([], ExtractionStatus.ERROR, product_id="p5")),
    ]
    run_batch._write_review_csv(predictions, tmp_path / "needs_review.csv")

    rows = _read_review_csv(tmp_path)
    reasons = {row["product_id"]: row["reason"] for row in rows}
    assert reasons == {"p4": "required_missing", "p5": "card_error"}
    assert all(row["attribute_code"] == "" for row in rows)


def test_review_csv_sanitizes_formula_cells(tmp_path: Path) -> None:
    """Значения, начинающиеся с = + - @, получают префикс `'` (CSV-инъекция)."""
    from specflow_contracts import AttributeCandidate, ExtractionMethod, ExtractionStatus

    candidate = AttributeCandidate(
        attribute_code="model",
        raw_value="=1+1",
        normalized_value="=1+1",
        confidence=0.5,
        extraction_method=ExtractionMethod.NER,
        is_confirmed_in_text=True,
        ner_score=0.5,
        is_new_field=True,
    )
    run_batch._write_review_csv(
        [(None, _review_result([candidate], ExtractionStatus.LOW_CONFIDENCE))],
        tmp_path / "needs_review.csv",
    )

    rows = _read_review_csv(tmp_path)
    assert rows[0]["raw_value"] == "'=1+1"


def test_run_offline_writes_review_csv_summary(tmp_path: Path) -> None:
    """Сводка содержит путь needs_review.csv; файл создаётся всегда."""
    source = _write_csv(tmp_path)

    outcome = run_batch.run_offline(source, tmp_path)

    assert outcome["review_csv"] == tmp_path / "needs_review.csv"
    assert (tmp_path / "needs_review.csv").exists()

"""Метрики качества извлечения на gold-наборе (задача 3, attribute_extractor.md §8).

Примеры:

    python scripts/evaluate.py --gold gold/gold.jsonl --predictions /tmp/preds/predictions.jsonl
    python scripts/evaluate.py --gold gold/gold.jsonl --rerun --grounding-stats --out /tmp/m.json

Сопоставление по паре ``(product_id, attribute_code)``, сравнение exact-match
по ``normalized_value`` (пересечение множеств, совместимо с allow_multiple).
Пороги влияют только на статусы и ``needs_review``, не на состав
предсказаний; сетка порогов — отчёт о доле кандидатов на ручную проверку.
Взвешивание по трафику — отложено сознательно.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_SRC_DIR = _SERVICE_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from attribute_extractor.constants import (  # noqa: E402
    AUTO_THRESHOLD,
    EVALUATE_METRICS_JSON_NAME,
    EVALUATE_THRESHOLD_GRID,
)

_DEFAULT_GOLD = _SERVICE_DIR / "gold" / "gold.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Разобрать JSONL-файл в список словарей."""
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _gold_id(card: dict[str, Any]) -> str | None:
    """Идентификатор карточки gold: ``product_id`` либо ``sku_id``."""
    value = card.get("product_id") or card.get("sku_id")
    return str(value) if value is not None else None


def build_gold_map(records: list[dict[str, Any]]) -> dict[str, dict[str, set[str]]]:
    """Эталон: id карточки → код атрибута → множество канонических значений."""
    gold: dict[str, dict[str, set[str]]] = {}
    for record in records:
        product_id = _gold_id(record.get("card", {}))
        if product_id is None:
            continue
        values = gold.setdefault(product_id, {})
        for item in record.get("expected", []):
            values.setdefault(str(item["attribute_code"]), set()).add(str(item["normalized_value"]))
    return gold


def build_pred_map(results: list[dict[str, Any]]) -> dict[str, dict[str, set[str]]]:
    """Предсказания: id карточки → код атрибута → множество значений."""
    preds: dict[str, dict[str, set[str]]] = {}
    for result in results:
        product_id = result.get("product_id")
        if product_id is None:
            continue
        values = preds.setdefault(str(product_id), {})
        for attribute in result.get("attributes", []):
            values.setdefault(str(attribute["attribute_code"]), set()).add(
                str(attribute["normalized_value"])
            )
    return preds


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def compute_counts(
    gold: dict[str, dict[str, set[str]]], preds: dict[str, dict[str, set[str]]]
) -> dict[str, tuple[int, int, int]]:
    """TP/FP/FN по каждому коду атрибута (пересечение множеств значений)."""
    counts: dict[str, tuple[int, int, int]] = {}
    codes = {code for values in gold.values() for code in values}
    codes |= {code for values in preds.values() for code in values}
    for code in sorted(codes):
        tp = fp = fn = 0
        for product_id in set(gold) | set(preds):
            gold_values = gold.get(product_id, {}).get(code, set())
            pred_values = preds.get(product_id, {}).get(code, set())
            tp += len(gold_values & pred_values)
            fp += len(pred_values - gold_values)
            fn += len(gold_values - pred_values)
        counts[code] = (tp, fp, fn)
    return counts


def attribute_metrics(counts: dict[str, tuple[int, int, int]]) -> dict[str, dict[str, float]]:
    """P/R/F1 и support по кодам атрибутов."""
    return {
        code: {
            "precision": _prf(tp, fp, fn)[0],
            "recall": _prf(tp, fp, fn)[1],
            "f1": _prf(tp, fp, fn)[2],
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }
        for code, (tp, fp, fn) in counts.items()
    }


def _macro_average(metrics: dict[str, dict[str, float]]) -> dict[str, float]:
    """Макро-усреднение P/R/F1 по кодам атрибутов."""
    if not metrics:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    return {
        key: sum(entry[key] for entry in metrics.values()) / len(metrics)
        for key in ("precision", "recall", "f1")
    }


def _micro_average(counts: dict[str, tuple[int, int, int]]) -> dict[str, float]:
    """Микро-усреднение: суммы TP/FP/FN по всем кодам."""
    tp = sum(entry[0] for entry in counts.values())
    fp = sum(entry[1] for entry in counts.values())
    fn = sum(entry[2] for entry in counts.values())
    precision, recall, f1 = _prf(tp, fp, fn)
    return {"precision": precision, "recall": recall, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def coverage_metrics(
    gold: dict[str, dict[str, set[str]]], preds: dict[str, dict[str, set[str]]]
) -> dict[str, float]:
    """Доля карточек, в которых атрибут предсказан (по всем карточкам gold)."""
    if not gold:
        return {}
    return {
        code: sum(1 for values in preds.values() if code in values) / len(gold)
        for code in sorted({code for values in preds.values() for code in values})
    }


def category_breakdown(
    records: list[dict[str, Any]],
    gold: dict[str, dict[str, set[str]]],
    preds: dict[str, dict[str, set[str]]],
) -> dict[str, dict[str, dict[str, float]]]:
    """Метрики отдельно по каждой категории (stratified по gold)."""
    categories = {
        _gold_id(record.get("card", {})): str(record["card"].get("category_name") or "")
        for record in records
        if _gold_id(record.get("card", {})) is not None
    }
    breakdown: dict[str, dict[str, dict[str, float]]] = {}
    for category in sorted(set(categories.values())):
        product_ids = [pid for pid, cat in categories.items() if cat == category]
        gold_part = {pid: gold[pid] for pid in product_ids if pid in gold}
        preds_part = {pid: preds[pid] for pid in product_ids if pid in preds}
        breakdown[category] = attribute_metrics(compute_counts(gold_part, preds_part))
    return breakdown


def below_threshold_shares(
    results: list[dict[str, Any]], thresholds: tuple[float, ...] = EVALUATE_THRESHOLD_GRID
) -> dict[str, float]:
    """Доля кандидатов с ``confidence`` ниже порога — нагрузка ручной проверки."""
    confidences = [
        float(attribute["confidence"])
        for result in results
        for attribute in result.get("attributes", [])
    ]
    if not confidences:
        return {str(threshold): 0.0 for threshold in thresholds}
    return {
        str(threshold): sum(1 for value in confidences if value < threshold) / len(confidences)
        for threshold in thresholds
    }


def grounding_stats(gold_path: Path) -> dict[str, float | int]:
    """Доля кандидатов, отброшенных grounding (два прогона пайплайна).

    Сравниваются суммарные числа атрибутов при ``grounding_required=true`` и
    ``false``; сам пайплайн не модифицируется.
    """
    from attribute_extractor.config import Settings
    from attribute_extractor.pipeline import ExtractPipeline

    records = load_jsonl(gold_path)
    totals: dict[bool, int] = {}
    for grounding_required in (False, True):
        settings = Settings(grounding_required=grounding_required)
        pipeline = ExtractPipeline(settings=settings)
        total = 0
        for record in records:
            card = _record_card(record)
            if card is not None:
                total += len(pipeline.extract(card).attributes)
        totals[grounding_required] = total
    before, after = totals[False], totals[True]
    return {
        "candidates_before": before,
        "candidates_after": after,
        "share_filtered": (before - after) / before if before else 0.0,
    }


def _record_card(record: dict[str, Any]) -> Any:
    """Карточка из gold-записи (модель контракта) либо ``None``."""
    from specflow_contracts import ProductCard

    data = record.get("card", {})
    if not (data.get("title") or data.get("description")):
        return None
    return ProductCard(
        product_id=_gold_id(data),
        title=data.get("title"),
        description=data.get("description"),
        category_id=data.get("category_id"),
        category_name=data.get("category_name"),
    )


def rerun_predictions(gold_path: Path) -> list[dict[str, Any]]:
    """Прогнать пайплайн по gold-карточкам (когда predictions.jsonl нет)."""
    from attribute_extractor.config import Settings
    from attribute_extractor.pipeline import ExtractPipeline

    pipeline = ExtractPipeline(settings=Settings())
    results = []
    for record in load_jsonl(gold_path):
        card = _record_card(record)
        if card is not None:
            results.append(pipeline.extract(card).model_dump())
    return results


def build_report(
    records: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    grounding: dict[str, float | int] | None = None,
) -> dict[str, Any]:
    """Собрать полный отчёт метрик (структура для stdout и metrics.json)."""
    gold = build_gold_map(records)
    preds = build_pred_map(results)
    counts = compute_counts(gold, preds)
    metrics = attribute_metrics(counts)
    report: dict[str, Any] = {
        "products": len(gold),
        "per_attribute": metrics,
        "macro": _macro_average(metrics),
        "micro": _micro_average(counts),
        "coverage": coverage_metrics(gold, preds),
        "categories": category_breakdown(records, gold, preds),
        "below_threshold": below_threshold_shares(results),
        "auto_threshold": AUTO_THRESHOLD,
    }
    if grounding is not None:
        report["grounding"] = grounding
    return report


def format_report(report: dict[str, Any]) -> str:
    """Человекочитаемая таблица метрик (без сторонних зависимостей)."""
    lines = [
        f"Карточек: {report['products']}  (порог авто-принятия: {report['auto_threshold']})",
        f"{'атрибут':<20}{'P':>7}{'R':>7}{'F1':>7}{'TP':>5}{'FP':>5}{'FN':>5}{'cov':>7}",
    ]
    for code, entry in report["per_attribute"].items():
        coverage = report["coverage"].get(code, 0.0)
        lines.append(
            f"{code:<20}{entry['precision']:>7.2f}{entry['recall']:>7.2f}"
            f"{entry['f1']:>7.2f}{entry['tp']:>5}{entry['fp']:>5}{entry['fn']:>5}"
            f"{coverage:>7.2f}"
        )
    macro, micro = report["macro"], report["micro"]
    lines.append(
        f"{'макро':<20}{macro['precision']:>7.2f}{macro['recall']:>7.2f}{macro['f1']:>7.2f}"
    )
    lines.append(
        f"{'микро':<20}{micro['precision']:>7.2f}{micro['recall']:>7.2f}{micro['f1']:>7.2f}"
    )
    lines.append("Доля кандидатов ниже порога (нагрузка ручной проверки):")
    for threshold, share in report["below_threshold"].items():
        lines.append(f"  {threshold}: {share:.2%}")
    if "grounding" in report:
        grounding = report["grounding"]
        lines.append(
            f"Grounding: отброшено {grounding['share_filtered']:.2%} кандидатов "
            f"({grounding['candidates_after']} из {grounding['candidates_before']})"
        )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Метрики качества извлечения на gold-наборе.")
    parser.add_argument("--gold", type=Path, default=_DEFAULT_GOLD, help="Путь к gold.jsonl.")
    parser.add_argument(
        "--predictions",
        type=Path,
        default=None,
        help="predictions.jsonl из run_batch.py; по умолчанию пайплайн прогоняется заново.",
    )
    parser.add_argument(
        "--grounding-stats",
        action="store_true",
        help="Оценить долю кандидатов, отброшенных grounding (дополнительные прогоны).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"Путь к metrics.json (по умолчанию {EVALUATE_METRICS_JSON_NAME} не пишется).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.gold.exists():
        print(f"gold-файл не найден: {args.gold}", file=sys.stderr)
        return 1
    records = load_jsonl(args.gold)
    if args.predictions is not None:
        if not args.predictions.exists():
            print(f"файл предсказаний не найден: {args.predictions}", file=sys.stderr)
            return 1
        results = load_jsonl(args.predictions)
        grounding = grounding_stats(args.gold) if args.grounding_stats else None
    else:
        results = rerun_predictions(args.gold)
        grounding = grounding_stats(args.gold) if args.grounding_stats else None
    report = build_report(records, results, grounding=grounding)
    print(format_report(report))
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"metrics: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

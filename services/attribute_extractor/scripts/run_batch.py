"""Офлайн-прогон пайплайна извлечения по файлу карточек (задача 2).

Примеры:

    python scripts/run_batch.py gold/gold.jsonl --out /tmp/preds
    python scripts/run_batch.py cards.csv --out /tmp/preds --csv --max-items 10

По умолчанию работает офлайн, без HTTP: карточки из входного файла проходят
через ``ExtractPipeline`` напрямую. Настройки пайплайна — из переменных
окружения ``EXTRACTOR_*``. Выход — ``predictions.jsonl`` (сериализованные
``ExtractionResult`` — вход для scripts/evaluate.py), очередь ручной проверки
``needs_review.csv`` (всегда) и опционально CSV в формате PredictionRow
(``--csv``).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_SRC_DIR = _SERVICE_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from attribute_extractor.constants import (  # noqa: E402
    AUTO_THRESHOLD,
    CONFLICT_FEATURE_KEY,
    CONFLICT_VALUES_KEY,
    FEATURE_CHARACTERISTIC,
    REVIEW_CSV_COLUMNS,
    RUN_BATCH_CSV_BASE_COLUMNS,
    RUN_BATCH_CSV_NAME,
    RUN_BATCH_DEFAULT_BATCH_SIZE,
    RUN_BATCH_INPUT_SUFFIXES,
    RUN_BATCH_JSONL_NAME,
    RUN_BATCH_MAX_BATCH_SIZE,
    RUN_BATCH_MAX_INPUT_SIZE_MB,
    RUN_BATCH_REVIEW_CSV_NAME,
)

logger = logging.getLogger(__name__)

_JSON_SUFFIXES = frozenset({".json", ".jsonl"})
_TABLE_SUFFIXES = frozenset({".csv", ".tsv"})


def _load_rows(path: Path) -> list[dict[str, Any]]:
    """Разобрать входной файл в строки-карточки.

    ``.csv``/``.tsv`` — таблицы; ``.json``/``.jsonl`` — JSON-массив либо поток
    JSON-объектов по строкам (gold-формат ``gold.jsonl``).
    """
    suffix = path.suffix.lower()
    if suffix in _TABLE_SUFFIXES:
        delimiter = "\t" if suffix == ".tsv" else ","
        with path.open(encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle, delimiter=delimiter)]
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _row_to_card(row: dict[str, Any]) -> tuple[Any, str | None]:
    """Карточка из строки входа и ошибка разбора (если есть).

    Понимает gold-формат с обёрткой ``{"card": {...}, "sku_id": ...}``.
    Невалидный JSON в ``seller_attributes`` → карточка без seller-атрибутов
    плюс непустая ошибка: вызывающий присвоит ``status=error``, но сохранит
    title/category для CSV-выгрузки.
    """
    from specflow_contracts import ProductCard

    data = row.get("card", row)
    seller = data.get("seller_attributes")
    parse_error = None
    if isinstance(seller, str):
        seller = seller.strip() or None  # пустая ячейка CSV — не атрибуты
    if isinstance(seller, str):
        try:
            seller = json.loads(seller)
        except json.JSONDecodeError as error:
            seller = None
            parse_error = f"невалидный JSON в seller_attributes: {error}"
    card = ProductCard(
        product_id=data.get("product_id") or data.get("sku_id"),
        title=data.get("title"),
        description=data.get("description"),
        seller_attributes=seller,
        category_id=data.get("category_id"),
        category_name=data.get("category_name"),
    )
    return card, parse_error


def _error_result(card: Any, pipeline_version: str) -> Any:
    """``ExtractionResult`` со ``status=error`` для неразобранной карточки."""
    from specflow_contracts import ExtractionResult, ExtractionStatus

    return ExtractionResult(
        attributes=[],
        status=ExtractionStatus.ERROR,
        needs_review=True,
        pipeline_version=pipeline_version,
        product_id=card.product_id if card is not None else None,
        category_id=card.category_id if card is not None else None,
        category_name=card.category_name if card is not None else None,
        low_confidence_count=0,
        processing_time_ms=0,
    )


def _write_jsonl(predictions: list[tuple[Any, Any]], path: Path) -> None:
    """По одной строке на карточку: сериализованный ``ExtractionResult``."""
    with path.open("w", encoding="utf-8") as handle:
        for _, result in predictions:
            handle.write(result.model_dump_json() + "\n")


def _write_csv(predictions: list[tuple[Any, Any]], path: Path) -> None:
    """CSV в формате PredictionRow: базовые колонки + пара на каждый атрибут."""
    codes = sorted(
        {attribute.attribute_code for _, result in predictions for attribute in result.attributes}
    )
    fieldnames = list(RUN_BATCH_CSV_BASE_COLUMNS) + [
        column for code in codes for column in (code, f"{code}_confidence")
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for card, result in predictions:
            row: dict[str, Any] = {
                "product_id": result.product_id or "",
                "title": card.title if card is not None else "",
                "category": result.category_name or "",
                "needs_review": result.needs_review,
                "status": result.status.value,
            }
            for attribute in result.attributes:
                row[attribute.attribute_code] = attribute.normalized_value
                row[f"{attribute.attribute_code}_confidence"] = attribute.confidence
            writer.writerow(row)


def _sanitize_csv_cell(value: Any) -> Any:
    """Нейтрализовать формулы Excel/Sheets: файл ревью открывают вручную.

    Текстовые ячейки, начинающиеся с ``= + - @`` или табуляции, получают
    префикс ``'`` — стандартная защита от CSV-инъекций.
    """
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{value}"
    return value


def _candidate_reasons(candidate: Any) -> list[str]:
    """Причины ручной проверки кандидата (одна строка review-CSV на причину)."""
    reasons: list[str] = []
    if candidate.is_new_field:
        reasons.append("new_field")
    if candidate.confidence < AUTO_THRESHOLD:
        reasons.append("low_confidence")
    if candidate.features and CONFLICT_FEATURE_KEY in candidate.features:
        reasons.append("conflict")
    return reasons


_CARD_REVIEW_REASONS = {
    "partial": "required_missing",
    "error": "card_error",
    "skipped": "skipped",
}


def _write_review_csv(predictions: list[tuple[Any, Any]], path: Path) -> None:
    """Очередь ручной проверки: все ``needs_review``-карточки прогона.

    Кандидаты пишутся по строке на причину (``new_field``/``low_confidence``/
    ``conflict``); карточные причины без кандидата (незакрытые обязательные,
    ошибка разбора, пропуск) — одной строкой с пустыми значениями. Колонка
    ``decision`` остаётся пустой для ручных отметок при разборе.
    """
    with path.open("w", encoding="utf-8", newline="") as handle:
        columns: list[str] = list(REVIEW_CSV_COLUMNS)
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for _card, result in predictions:
            if not result.needs_review:
                continue
            base = {
                "product_id": result.product_id or "",
                "category_name": result.category_name or "",
                "status": result.status.value,
            }
            emitted = False
            for candidate in result.attributes:
                characteristic = ""
                conflict_values = ""
                if candidate.features:
                    characteristic = str(candidate.features.get(FEATURE_CHARACTERISTIC) or "")
                    values = candidate.features.get(CONFLICT_VALUES_KEY)
                    if isinstance(values, list):
                        # Победитель первым (merging) — первым виден в ячейке.
                        conflict_values = " vs ".join(str(value) for value in values)
                for reason in _candidate_reasons(candidate):
                    row: dict[str, Any] = {column: "" for column in REVIEW_CSV_COLUMNS}
                    row.update(base)
                    row.update(
                        {
                            "reason": reason,
                            "attribute_code": candidate.attribute_code,
                            "characteristic": characteristic,
                            "conflict_values": conflict_values,
                            "raw_value": candidate.raw_value,
                            "normalized_value": candidate.normalized_value,
                            "confidence": candidate.confidence,
                            "ner_score": candidate.ner_score,
                            "match_score": candidate.match_score,
                            "is_new_field": candidate.is_new_field,
                            "extraction_method": candidate.extraction_method.value,
                            "evidence_text": candidate.evidence_text or "",
                            "span_start": (
                                candidate.source_spans[0].start if candidate.source_spans else None
                            ),
                            "span_end": (
                                candidate.source_spans[0].end if candidate.source_spans else None
                            ),
                            "decision": "",
                        }
                    )
                    writer.writerow({key: _sanitize_csv_cell(value) for key, value in row.items()})
                    emitted = True
            if not emitted:
                row = {column: "" for column in REVIEW_CSV_COLUMNS}
                row.update(base)
                row["reason"] = _CARD_REVIEW_REASONS.get(result.status.value, result.status.value)
                writer.writerow({key: _sanitize_csv_cell(value) for key, value in row.items()})


def validate_input(path: Path) -> str | None:
    """Причина отказа по входному файлу либо ``None``, если файл пригоден.

    Проверки по аналогии с bulk-загрузкой фронтенда (frontend.md): файл
    непустой, разумного размера, расширение распознано.
    """
    if not path.exists() or not path.is_file():
        return f"файл не найден: {path}"
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb == 0:
        return f"файл пуст: {path}"
    if size_mb > RUN_BATCH_MAX_INPUT_SIZE_MB:
        return f"файл больше {RUN_BATCH_MAX_INPUT_SIZE_MB} МБ: {path}"
    if path.suffix.lower() not in RUN_BATCH_INPUT_SUFFIXES:
        supported = ", ".join(RUN_BATCH_INPUT_SUFFIXES)
        return f"расширение {path.suffix!r} не распознано (поддерживаются: {supported})"
    return None


def run_offline(
    input_path: Path,
    out_dir: Path,
    *,
    batch_size: int = RUN_BATCH_DEFAULT_BATCH_SIZE,
    max_items: int | None = None,
    write_csv: bool = False,
) -> dict[str, Any]:
    """Прогнать карточки файла через ``ExtractPipeline`` и записать артефакты.

    Поток обрабатывается частями по ``batch_size``; одна битая карточка даёт
    ``status=error`` и не прерывает прогон (частичный успех). Возвращает
    сводку ``{total, errors, jsonl, csv}``.
    """
    from attribute_extractor.config import Settings
    from attribute_extractor.pipeline import ExtractPipeline

    settings = Settings()
    pipeline = ExtractPipeline(settings=settings)
    rows = _load_rows(input_path)
    if max_items is not None:
        rows = rows[:max_items]

    predictions: list[tuple[Any, Any]] = []
    for start in range(0, len(rows), batch_size):
        for row in rows[start : start + batch_size]:
            card, parse_error = _row_to_card(row)
            if parse_error is not None:
                predictions.append((card, _error_result(card, settings.pipeline_version)))
                continue
            try:
                predictions.append((card, pipeline.extract(card)))
            except Exception:  # noqa: BLE001 — карточка с битым пайплайном не прерывает прогон
                # Ошибка пайплайна не прерывает прогон остальных карточек
                # (частичный успех), но причина фиксируется в логе с traceback.
                logger.exception(
                    "Извлечение не удалось (product_id=%s); карточка помечена error",
                    card.product_id,
                )
                predictions.append((card, _error_result(card, settings.pipeline_version)))

    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / RUN_BATCH_JSONL_NAME
    _write_jsonl(predictions, jsonl_path)
    csv_path = None
    if write_csv:
        csv_path = out_dir / RUN_BATCH_CSV_NAME
        _write_csv(predictions, csv_path)
    review_path = out_dir / RUN_BATCH_REVIEW_CSV_NAME
    _write_review_csv(predictions, review_path)
    return {
        "total": len(predictions),
        "errors": sum(1 for _, result in predictions if result.status.value == "error"),
        "jsonl": jsonl_path,
        "csv": csv_path,
        "review_csv": review_path,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Офлайн-прогон пайплайна извлечения по файлу карточек."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Входной файл .csv/.tsv/.json/.jsonl с карточками.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("."),
        help="Каталог для predictions.jsonl (и predictions.csv по --csv).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=RUN_BATCH_DEFAULT_BATCH_SIZE,
        help=f"Размер части потока (1..{RUN_BATCH_MAX_BATCH_SIZE}).",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Обработать только первые N карточек (быстрая проба).",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Дополнительно записать predictions.csv в формате PredictionRow.",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.batch_size <= RUN_BATCH_MAX_BATCH_SIZE:
        parser.error(f"--batch-size должен быть в диапазоне 1..{RUN_BATCH_MAX_BATCH_SIZE}")
    if args.max_items is not None and args.max_items < 1:
        parser.error("--max-items должен быть больше 0")
    return args


def main(argv: list[str] | None = None) -> int:
    # Логи пайплайна (деградации, сбои карточек) должны быть видны в CLI;
    # basicConfig — no-op, если логирование уже настроено вызывающим кодом.
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args(argv)
    error = validate_input(args.input)
    if error is not None:
        print(error, file=sys.stderr)
        return 1
    started = time.monotonic()
    outcome = run_offline(
        args.input,
        args.out,
        batch_size=args.batch_size,
        max_items=args.max_items,
        write_csv=args.csv,
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    print(
        f"predictions: {outcome['jsonl']} "
        f"({outcome['total']} карточек, ошибок: {outcome['errors']}, {elapsed_ms} мс)"
    )
    if outcome["csv"] is not None:
        print(f"csv: {outcome['csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

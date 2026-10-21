"""CLI: собрать gold-набор расширения из вручную составленных карточек.

Источник — ``gold/curated_cards.json``: карточки с ожидаемыми значениями,
пометками и тегами. Скрипт не доверяет разметке и проверяет её:

* структура записи (``validate_gold``);
* подтверждение каждого ожидаемого значения текстом карточки (``grounding_errors``);
* отсутствие пересечения ``sku_id`` с базовым корпусным gold-набором;
* размер hard set в допустимом диапазоне (``validate_hard_set``).

Результат:

* ``gold/gold_expansion.jsonl`` — карточки расширения (``source=curated``);
* ``gold/hard_set.jsonl`` — подмножество карточек с меткой ``hard``.

Seller-атрибуты в gold-запись не попадают (вход пайплайна — только title и
description, см. README, раздел 4): они остаются в исходном JSON как
источник разметки и как основание для исключения значений, которых нет в
тексте.

Запуск из корня репозитория:

    PYTHONPATH=services/attribute_extractor/src:services/contracts/src \\
        python services/attribute_extractor/scripts/build_gold_curated.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_SRC_DIR = _SERVICE_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from attribute_extractor.constants import GOLD_SOURCE_CURATED  # noqa: E402
from attribute_extractor.gold_sampling import (  # noqa: E402
    existing_sku_ids,
    grounding_errors,
    hard_set_records,
    validate_gold,
    validate_hard_set,
)

_DEFAULT_SOURCE = _SERVICE_DIR / "gold" / "curated_cards.json"
_DEFAULT_OUT = _SERVICE_DIR / "gold" / "gold_expansion.jsonl"
_DEFAULT_OUT_HARD = _SERVICE_DIR / "gold" / "hard_set.jsonl"
_DEFAULT_GOLD = _SERVICE_DIR / "gold" / "gold.jsonl"


def load_source(path: Path) -> list[dict[str, Any]]:
    """Прочитать исходный JSON с curated-карточками."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    cards = payload.get("cards") if isinstance(payload, Mapping) else None
    if not isinstance(cards, list):
        raise SystemExit(f"{path}: ожидается объект с полем cards (список карточек)")
    return [dict(card) for card in cards if isinstance(card, Mapping)]


def _expected_items(card: Mapping[str, Any]) -> list[dict[str, str]]:
    """Привести ``expected`` к списку пар ``attribute_code``/``normalized_value``.

    В исходном файле разметка записана компактным словарём
    (``{"brand": "Samsung"}``) — так легче читать и вычитывать руками;
    в gold-запись попадает канонический список.
    """
    expected = card.get("expected")
    if isinstance(expected, Mapping):
        return [
            {"attribute_code": str(code), "normalized_value": str(value)}
            for code, value in expected.items()
        ]
    return [
        {
            "attribute_code": str(item.get("attribute_code") or ""),
            "normalized_value": str(item.get("normalized_value") or ""),
        }
        for item in (expected or [])
    ]


def build_record(card: Mapping[str, Any]) -> dict[str, Any]:
    """Gold-запись из curated-карточки.

    Формат совпадает с ``gold/gold.jsonl``; дополнительно проставляются
    ``source`` (происхождение карточки) и ``tags`` (метки сложности).
    """
    tags = [str(tag) for tag in (card.get("tags") or [])]
    return {
        "card": {
            "sku_id": str(card.get("sku_id") or ""),
            "category_id": str(card.get("category_id") or ""),
            "category_name": str(card.get("category_name") or ""),
            "title": str(card.get("title") or ""),
            "description": str(card.get("description") or ""),
        },
        "expected": _expected_items(card),
        "notes": str(card.get("notes") or ""),
        "source": str(card.get("source") or GOLD_SOURCE_CURATED),
        "tags": tags,
    }


def write_jsonl(path: Path, records: list[Mapping[str, Any]]) -> None:
    """Записать список записей в JSONL (по записи на строку)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def ungrounded_seller_values(card: Mapping[str, Any]) -> list[str]:
    """Значения seller-атрибутов, не встречающихся в тексте карточки.

    Служебная диагностика: такие значения не должны попадать в ``expected``
    (вход пайплайна — только текст), и по ним видно, какие характеристики
    реально приходится вытаскивать из параметров продавца.
    """
    text = f"{card.get('title') or ''} {card.get('description') or ''}".casefold()
    missing: list[str] = []
    seller_attributes = card.get("seller_attributes") or {}
    if not isinstance(seller_attributes, Mapping):
        return missing
    for name, value in seller_attributes.items():
        raw = str(value).strip()
        if not raw:
            continue
        if raw.casefold() not in text:
            missing.append(f"{name}={raw}")
    return missing


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Сборка gold-набора расширения.")
    parser.add_argument("--source", type=Path, default=_DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    parser.add_argument("--out-hard", type=Path, default=_DEFAULT_OUT_HARD)
    parser.add_argument(
        "--gold",
        type=Path,
        default=_DEFAULT_GOLD,
        help="базовый gold-набор: проверяется отсутствие пересечения sku_id",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="только проверить разметку, ничего не записывая",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.source.exists():
        print(f"исходный файл не найден: {args.source}", file=sys.stderr)
        return 1

    cards = load_source(args.source)
    records = [build_record(card) for card in cards]

    errors: list[str] = []
    errors.extend(validate_gold(records))
    errors.extend(grounding_errors(records))

    hard_records = hard_set_records(records)
    errors.extend(validate_hard_set(hard_records))

    if args.gold.exists():
        base_records = [
            json.loads(line)
            for line in args.gold.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        overlap = existing_sku_ids(base_records) & existing_sku_ids(records)
        if overlap:
            errors.append(
                "sku_id пересекаются с базовым gold-набором: "
                + ", ".join(sorted(overlap)[:10])
            )

    if errors:
        print(f"ошибок разметки: {len(errors)}", file=sys.stderr)
        for error in errors[:50]:
            print(f"  {error}", file=sys.stderr)
        if len(errors) > 50:
            print(f"  ... ещё {len(errors) - 50}", file=sys.stderr)
        return 1

    if not args.check:
        write_jsonl(args.out, records)
        write_jsonl(args.out_hard, hard_records)

    categories = Counter(str(card.get("category_name") or "без категории") for card in cards)
    codes = Counter(
        str(item.get("attribute_code") or "")
        for card in cards
        for item in _expected_items(card)
    )
    missing_seller_values = sum(
        len(ungrounded_seller_values(card)) for card in cards
    )
    print(f"карточек: {len(records)} (hard: {len(hard_records)})")
    print(f"категорий: {len(categories)}")
    for name, count in categories.most_common():
        print(f"  {name}: {count}")
    print("атрибуты:")
    for code, count in sorted(codes.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {code}: {count}")
    print(
        f"значений продавца, отсутствующих в тексте: {missing_seller_values} "
        "(в expected не попадают)"
    )
    if not args.check:
        print(f"расширение: {args.out}")
        print(f"hard set: {args.out_hard}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

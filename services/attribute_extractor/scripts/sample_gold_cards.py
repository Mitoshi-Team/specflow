"""CLI: собрать черновик gold-набора (карточки для ручной разметки).

Формирует детерминированный стратифицированный сэмпл карточек из EDA-выгрузок
(``skus.pkl`` + ``sku_desc.parquet``) в формате gold-набора (README, раздел 4)
с пустым ``expected`` — значения проставляет человек.

Запуск из корня репозитория (нужны pandas/pyarrow):

    PYTHONPATH=services/attribute_extractor/src:services/contracts/src \\
        python services/attribute_extractor/scripts/sample_gold_cards.py \\
        --out services/attribute_extractor/gold/gold.jsonl
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from attribute_extractor.gold_sampling import (
    GOLD_CATEGORY_QUOTAS,
    GOLD_EXPANSION_QUOTAS,
    GOLD_EXPANSION_SEED,
    GOLD_SAMPLE_SIZE,
    GOLD_SEED,
    existing_sku_ids,
    is_usable,
    parse_offer_params,
    select_diverse,
)
from attribute_extractor.safe_io import load_pickle_file

DEFAULT_DATASET_DIR = Path("EDA/dataset")

QUOTAS_PRESETS: dict[str, Mapping[str, int] | None] = {
    "base": GOLD_CATEGORY_QUOTAS,
    "expansion": GOLD_EXPANSION_QUOTAS,
    "none": None,
}
"""Пресеты квот категорий: ``base`` — исходный gold, ``expansion`` — расширение."""


def _offer_category_id(offer: dict[str, Any]) -> str:
    categories = offer.get("categories")
    category_id = categories.get("categoryId") if isinstance(categories, dict) else None
    return str(category_id) if category_id is not None else ""


def load_cards(dataset_dir: Path) -> list[dict[str, Any]]:
    """Собрать карточки из YML-каталога и текстовых описаний.

    ``skus.pkl`` десериализуется ограниченным unpickler (``safe_io``): файл
    данных может прийти из внешнего источника, и pickle-объекты исполняют
    код — разрешены только встроенные типы.
    """
    raw = load_pickle_file(dataset_dir / "skus.pkl")
    shop = raw["yml_catalog"]["shop"]
    offers = shop["offers"]["offer"]
    category_names = {
        str(category["@id"]): str(category["#text"]) for category in shop["categories"]["category"]
    }

    descriptions = pd.read_parquet(
        dataset_dir / "sku_desc.parquet", columns=["sku_id", "title", "description"]
    )
    by_sku = {
        str(row.sku_id): (row.title, row.description)
        for row in descriptions.itertuples(index=False)
    }

    cards: list[dict[str, Any]] = []
    for offer in offers:
        sku_id = str(offer.get("@id") or "")
        if sku_id not in by_sku:
            continue
        title, description = by_sku[sku_id]
        category_id = _offer_category_id(offer)
        cards.append(
            {
                "sku_id": sku_id,
                "category_id": category_id,
                "category_name": category_names.get(category_id, ""),
                "vendor": str(offer.get("vendor") or ""),
                "title": title if isinstance(title, str) else "",
                "description": description if isinstance(description, str) else "",
                "seller_attributes": parse_offer_params(offer),
            }
        )
    return cards


def build_record(card: Mapping[str, Any]) -> dict[str, Any]:
    """Черновик gold-записи: входная карточка без ожидаемых значений."""
    return {
        "card": {
            "sku_id": card["sku_id"],
            "category_id": card["category_id"],
            "category_name": card["category_name"],
            "title": card["title"],
            "description": card["description"],
            "seller_attributes": card["seller_attributes"],
        },
        "expected": [],
        "notes": None,
    }


def load_gold_sku_ids(paths: list[Path]) -> set[str]:
    """Собрать sku_id из существующих gold-файлов.

    Файлы читаются построчно как JSONL: один битый файл не должен ронять
    сэмплирование целиком, поэтому нечитаемые строки пропускаются с
    предупреждением.
    """
    skus: set[str] = set()
    for path in paths:
        if not path.exists():
            print(f"файл исключений не найден, пропускаю: {path}")
            continue
        records: list[Mapping[str, Any]] = []
        with path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"{path}:{line_number}: строка не разобрана как JSON, пропускаю")
        skus |= existing_sku_ids(records)
    return skus


def has_labeled_records(path: Path) -> bool:
    """Есть ли в файле записи с непустым ``expected`` (то есть размеченный gold)."""
    if not path.exists():
        return False
    with path.open(encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("expected"):
                return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Сэмпл карточек для gold-набора")
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="число карточек (по умолчанию — размер пресета квот)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="seed сэмплирования (по умолчанию — seed пресета квот)",
    )
    parser.add_argument(
        "--quotas-preset",
        choices=sorted(QUOTAS_PRESETS),
        default="base",
        help="пресет квот категорий (по умолчанию base — квоты исходного gold)",
    )
    parser.add_argument(
        "--exclude",
        type=Path,
        action="append",
        default=[],
        metavar="GOLD_JSONL",
        help="gold-файл, карточки которого исключаются из сэмпла (можно указать несколько)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="разрешить перезапись файла с размеченными значениями",
    )
    args = parser.parse_args()

    if args.out.exists() and not args.force and has_labeled_records(args.out):
        raise SystemExit(
            f"{args.out} содержит размеченные значения (expected не пуст); "
            "перезапись запрещена — используйте --force или другой --out"
        )

    quotas = QUOTAS_PRESETS[args.quotas_preset]
    if args.quotas_preset == "expansion":
        default_seed, default_count = GOLD_EXPANSION_SEED, sum(GOLD_EXPANSION_QUOTAS.values())
    else:
        default_seed, default_count = GOLD_SEED, GOLD_SAMPLE_SIZE
    seed = args.seed if args.seed is not None else default_seed
    count = args.count if args.count is not None else default_count

    cards = [card for card in load_cards(args.dataset_dir) if is_usable(card)]
    excluded = load_gold_sku_ids(args.exclude)
    pool = [card for card in cards if str(card.get("sku_id") or "") not in excluded]
    selected = select_diverse(pool, count, seed=seed, quotas=quotas)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for card in selected:
            f.write(json.dumps(build_record(card), ensure_ascii=False) + "\n")

    categories = Counter(card["category_name"] or "без категории" for card in selected)
    print(f"карточек: {len(selected)} из {len(cards)} пригодных")
    print(f"исключено по --exclude: {len(excluded)}")
    print(f"категорий: {len(categories)}")
    for name, count in categories.most_common():
        print(f"  {name}: {count}")


if __name__ == "__main__":
    main()

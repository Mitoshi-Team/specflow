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
import pickle
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from attribute_extractor.gold_sampling import (
    GOLD_CATEGORY_QUOTAS,
    GOLD_SAMPLE_SIZE,
    GOLD_SEED,
    is_usable,
    parse_offer_params,
    select_diverse,
)

DEFAULT_DATASET_DIR = Path("EDA/dataset")


def _offer_category_id(offer: dict[str, Any]) -> str:
    categories = offer.get("categories")
    category_id = categories.get("categoryId") if isinstance(categories, dict) else None
    return str(category_id) if category_id is not None else ""


def load_cards(dataset_dir: Path) -> list[dict[str, Any]]:
    """Собрать карточки из YML-каталога и текстовых описаний."""
    with open(dataset_dir / "skus.pkl", "rb") as f:
        raw = pickle.load(f)
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Сэмпл карточек для gold-набора")
    parser.add_argument("--dataset-dir", type=Path, default=DEFAULT_DATASET_DIR)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--count", type=int, default=GOLD_SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=GOLD_SEED)
    args = parser.parse_args()

    cards = [card for card in load_cards(args.dataset_dir) if is_usable(card)]
    selected = select_diverse(cards, args.count, seed=args.seed, quotas=GOLD_CATEGORY_QUOTAS)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for card in selected:
            f.write(json.dumps(build_record(card), ensure_ascii=False) + "\n")

    categories = Counter(card["category_name"] or "без категории" for card in selected)
    print(f"карточек: {len(selected)} из {len(cards)} пригодных")
    print(f"категорий: {len(categories)}")
    for name, count in categories.most_common():
        print(f"  {name}: {count}")


if __name__ == "__main__":
    main()

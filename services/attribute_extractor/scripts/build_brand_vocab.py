"""CLI-генератор бренд-словаря (BrandVocab) из офферов организаторов.

Источники: EDA/cache/offers_flat.parquet (vendor, category_id) и
EDA/cache/categories.parquet (category_name). Бренды считаются только по
фокус-категориям: вне их колонка vendor заполнена брендами-заглушками
продавцов («365home», «Krutoff»), релевантными нашему домену.

Слияние регистровых вариантов («Apple»/«APPLE»): сопоставление в BrandVocab
casefold-нуется, поэтому каноном становится самый частый вариант, а остальные
регистровые написания не дуб­лируются в regex.

Примеры:

    python scripts/build_brand_vocab.py
    python scripts/build_brand_vocab.py --source EDA --min-offers 5

По умолчанию пишет services/attribute_extractor/assets/brand_vocab.json
версонируемый ассет (data/ для генерируемых артефактов, не для словаря).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_SRC_DIR = _SERVICE_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

import pandas as pd  # noqa: E402

from attribute_extractor.constants import DEFAULT_BRAND_VOCAB_PATH  # noqa: E402

_REPO_ROOT = _SERVICE_DIR.parents[1]
MARKETPLACE_CATEGORIES = (
    "Смартфоны",
    "iPhone",
    "Ноутбуки",
    "Планшеты",
    "Телевизоры",
    "Мониторы",
    "Наушники",
    "Роботы-пылесосы",
)
JUNK_VENDOR_PATTERN = re.compile(r"^\W*$|^[0-9#]+$")
EXCLUDED_VENDORS = frozenset({"h", "f+", "hi"})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Собрать бренд-словарь из офферов.")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=_REPO_ROOT / "EDA" / "cache",
        help="Каталог с offers_flat.parquet и categories.parquet.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_REPO_ROOT / DEFAULT_BRAND_VOCAB_PATH,
        help="Путь к выходному brand_vocab.json.",
    )
    parser.add_argument(
        "--min-offers",
        type=int,
        default=5,
        help="Минимальное число офферов бренда в фокус-категориях.",
    )
    parser.add_argument(
        "--categories",
        nargs="*",
        default=list(MARKETPLACE_CATEGORIES),
        help="Фокус-категории для подсчёта брендов.",
    )
    return parser.parse_args(argv)


def collect_offers(cache_dir: Path, categories: list[str]) -> pd.DataFrame:
    offers = pd.read_parquet(cache_dir / "offers_flat.parquet")
    cats = pd.read_parquet(cache_dir / "categories.parquet")
    merged = offers.merge(cats, on="category_id", how="left")
    return merged[merged["category_name"].isin(categories)]


def build_vocab_entries(vendors: pd.Series, min_offers: int) -> list[str]:
    counts = vendors.fillna("").astype(str).str.strip().value_counts()
    counts = counts.drop(labels=[name for name in counts.index if name == ""], errors="ignore")
    counts = counts[counts >= min_offers]
    counts = counts[[name for name in counts.index if not JUNK_VENDOR_PATTERN.match(name)]]
    grouped: dict[str, list[tuple[str, int]]] = {}
    for name, count in counts.items():
        grouped.setdefault(name.casefold(), []).append((name, int(count)))
    names: list[str] = []
    for casefold_key, variants in grouped.items():
        if casefold_key in EXCLUDED_VENDORS:
            continue
        best_name, _ = max(variants, key=lambda item: item[1])
        names.append(best_name)
    return sorted(names)


def main() -> int:
    args = parse_args()
    offers = collect_offers(args.cache_dir, args.categories)
    if offers.empty:
        print("Нет офферов в фокус-категориях — проверьте cache-dir.", file=sys.stderr)
        return 1
    names = build_vocab_entries(offers["vendor"], args.min_offers)
    payload = {
        "names": names,
        "aliases": {},
        "stopwords": [],
        "category_count": len(args.categories),
        "offer_count": int(len(offers)),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Брендов: {len(names)} → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

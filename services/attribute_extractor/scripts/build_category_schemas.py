"""CLI-генератор реестра схем категорий из статистики каталога EDA/cache.

Примеры:

    python scripts/build_category_schemas.py
    python scripts/build_category_schemas.py --out data/category_schemas.json

Читает ``categories/offers_flat/cat_attr/param_stats.parquet`` из ``EDA/cache``
(результат ``EDA/src/run.py``) и пишет ``data/category_schemas.json``
(gitignored). Сервис загружает артефакт на старте (``SchemaRegistry.from_file``)
и отдаёт реальные схемы на ``/categories``; категории без схемы получают
generic-fallback. Пороги — ``CATEGORY_SCHEMA_REQUIRED_SHARE`` и
``CATEGORY_SCHEMA_MIN_CARDS`` в ``constants.py``.

Идемпотентен: повторный запуск при неизменном кэше даёт тот же результат.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_SRC_DIR = _SERVICE_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from attribute_extractor import category_schema_builder  # noqa: E402
from attribute_extractor.constants import (  # noqa: E402
    CATEGORY_SCHEMA_MIN_CARDS,
    CATEGORY_SCHEMA_REQUIRED_SHARE,
    DEFAULT_CATEGORY_SCHEMAS_PATH,
)

_REPO_ROOT = _SERVICE_DIR.parents[1]
_EDA_CACHE = _REPO_ROOT / "EDA" / "cache"

_INPUT_FILES = {
    "categories": _EDA_CACHE / "categories.parquet",
    "offers": _EDA_CACHE / "offers_flat.parquet",
    "cat_attr": _EDA_CACHE / "cat_attr.parquet",
    "param_stats": _EDA_CACHE / "param_stats.parquet",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Собрать data/category_schemas.json из статистики каталога EDA/cache."
    )
    parser.add_argument("--categories", type=Path, default=_INPUT_FILES["categories"])
    parser.add_argument("--offers", type=Path, default=_INPUT_FILES["offers"])
    parser.add_argument("--cat-attr", type=Path, default=_INPUT_FILES["cat_attr"])
    parser.add_argument("--param-stats", type=Path, default=_INPUT_FILES["param_stats"])
    parser.add_argument(
        "--out",
        type=Path,
        default=_REPO_ROOT / DEFAULT_CATEGORY_SCHEMAS_PATH,
        help="Путь к выходному category_schemas.json.",
    )
    parser.add_argument(
        "--required-share",
        type=float,
        default=CATEGORY_SCHEMA_REQUIRED_SHARE,
        help="Доля карточек категории, начиная с которой поле обязательное.",
    )
    parser.add_argument(
        "--min-cards",
        type=int,
        default=CATEGORY_SCHEMA_MIN_CARDS,
        help="Минимум карточек категории для построения схемы.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    inputs = {
        "categories": args.categories,
        "offers": args.offers,
        "cat_attr": args.cat_attr,
        "param_stats": args.param_stats,
    }
    missing = [f"{name}: {path}" for name, path in inputs.items() if not path.exists()]
    if missing:
        print(
            "Не найдены входные файлы EDA/cache (запустите EDA/src/run.py):\n  "
            + "\n  ".join(missing),
            file=sys.stderr,
        )
        return 1
    payload = category_schema_builder.build(
        categories_path=args.categories,
        offers_path=args.offers,
        cat_attr_path=args.cat_attr,
        param_stats_path=args.param_stats,
        required_share=args.required_share,
        min_cards=args.min_cards,
    )
    category_schema_builder.save(payload, args.out)
    required = sum(len(schema["required_attributes"]) for schema in payload["schemas"])
    optional = sum(len(schema["optional_attributes"]) for schema in payload["schemas"])
    print(
        f"schemas: {args.out} ({len(payload['schemas'])} категорий, "
        f"required={required}, optional={optional})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

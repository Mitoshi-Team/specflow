"""CLI-генератор персистентных каталога полей и блоклиста.

Примеры:

    python scripts/build_field_catalog.py
    python scripts/build_field_catalog.py --param-stats EDA/cache/param_stats.parquet

По умолчанию пишет ``data/field_catalog.json`` и ``data/field_blocklist.txt``
относительно корня репозитория. Идемпотентен: повторный запуск даёт тот же
результат (при неизменном seed/param-stats).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_SRC_DIR = _SERVICE_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from attribute_extractor import catalog_builder  # noqa: E402
from attribute_extractor.catalog_store import CatalogStore  # noqa: E402
from attribute_extractor.constants import (  # noqa: E402
    DEFAULT_FIELD_BLOCKLIST_PATH,
    DEFAULT_FIELD_CATALOG_PATH,
)

_REPO_ROOT = _SERVICE_DIR.parents[1]


def _default_path(relative: str) -> Path:
    return _REPO_ROOT / relative


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Собрать каталог полей и блоклист.")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=_default_path(DEFAULT_FIELD_CATALOG_PATH),
        help="Путь к выходному field_catalog.json.",
    )
    parser.add_argument(
        "--blocklist",
        type=Path,
        default=_default_path(DEFAULT_FIELD_BLOCKLIST_PATH),
        help="Путь к выходному field_blocklist.txt.",
    )
    parser.add_argument(
        "--param-stats",
        type=Path,
        default=None,
        help="Опциональный param_stats.parquet для обогащения синонимов/блоклиста.",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=catalog_builder.DEFAULT_ENRICH_MIN_COUNT,
        help="Минимальная частота имени атрибута при обогащении.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    catalog, blocklist = catalog_builder.build(
        param_stats_path=args.param_stats,
        min_count=args.min_count,
    )
    store = CatalogStore(args.catalog, args.blocklist)
    store.save_catalog(catalog)
    store.save_blocklist(blocklist)
    print(
        f"catalog: {args.catalog} ({len(catalog['entries'])} полей), "
        f"blocklist: {args.blocklist} ({len(blocklist)} записей)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

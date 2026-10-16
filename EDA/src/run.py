"""Оркестратор EDA: аналитика -> графики -> PDF-отчёт.

Запуск (в nix-shell с pandas/pyarrow/matplotlib/seaborn/reportlab):
    python EDA/src/run.py --stage all
    python EDA/src/run.py --stage analysis
    python EDA/src/run.py --stage figures
    python EDA/src/run.py --stage report
"""

from __future__ import annotations

import argparse
import time

from . import cards, catalog, config, coverage, traffic


def run_analysis(force: bool = False) -> None:
    stages = [
        ("cards", cards.run, config.CACHE_DIR / "cards_summary.json"),
        ("catalog", catalog.run, config.CACHE_DIR / "catalog_summary.json"),
        ("traffic", traffic.run, config.CACHE_DIR / "traffic_summary.json"),
        ("coverage", coverage.run, config.CACHE_DIR / "coverage_summary.json"),
    ]
    for name, fn, marker in stages:
        if marker.exists() and not force:
            print(f"[analysis] {name} skipped (cached)", flush=True)
            continue
        t0 = time.time()
        print(f"[analysis] {name} ...", flush=True)
        fn()
        print(f"[analysis] {name} done in {time.time() - t0:.1f}s", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--stage",
        choices=["all", "analysis", "figures", "report"],
        default="all",
    )
    ap.add_argument("--force", action="store_true", help="пересчитать аналитику заново")
    args = ap.parse_args()

    if args.stage in ("all", "analysis"):
        run_analysis(force=args.force)
    if args.stage in ("all", "figures"):
        from . import plotting

        plotting.run()
    if args.stage in ("all", "report"):
        from . import report

        report.run()


if __name__ == "__main__":
    main()

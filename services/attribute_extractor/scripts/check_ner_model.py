"""Проверка готовности каталога весов NER-модели.

Примеры:

    python services/attribute_extractor/scripts/check_ner_model.py
    python services/attribute_extractor/scripts/check_ner_model.py /app/models/ner

Скрипт используется и в docker-сборке (``services/attribute_extractor/
Dockerfile``): образ с нескачанными весами (указатели Git LFS) не должен
собираться — сервис деградировал бы до правил без явного диагноза.

Код возврата: 0 — каталог готов, 1 — есть проблемы.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SERVICE_DIR = Path(__file__).resolve().parents[1]
_SRC_DIR = _SERVICE_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from attribute_extractor.constants import DEFAULT_NER_MODEL_PATH  # noqa: E402
from attribute_extractor.ner_weights import check_model_dir  # noqa: E402
from attribute_extractor.paths import resolve_artifact_path  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """Проверить каталог весов и напечатать диагностику."""
    parser = argparse.ArgumentParser(description="Проверка каталога весов NER-модели")
    parser.add_argument(
        "path",
        nargs="?",
        default=DEFAULT_NER_MODEL_PATH,
        help="путь к каталогу модели (по умолчанию — %(default)s)",
    )
    args = parser.parse_args(argv)

    model_dir = resolve_artifact_path(args.path)
    problems = check_model_dir(model_dir)
    if problems:
        print(f"Каталог NER-модели не готов: {model_dir}", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print(f"Каталог NER-модели готов: {model_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

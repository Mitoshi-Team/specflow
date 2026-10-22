"""Резолв путей генерируемых артефактов независимо от рабочего каталога.

Часть дефолтных путей в ``constants.py`` исторически записана относительно
корня репозитория (``services/attribute_extractor/...``), часть — относительно
каталога сервиса (``data/``, ``models/``): сервис запускается и корня репо
(uvicorn из корня), и из каталога сервиса (скрипты, docker). Без согл-
сированного резолва артефакты терялись молча при запуске не из той базы:
бренд-словарь не грузился (в gold 100 FN по brand), каталог полей
создавался заново пустым.
"""

from __future__ import annotations

from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]
"""Корень сервиса: ``src/attribute_extractor/paths.py`` → каталог сервиса."""

REPO_ROOT = SERVICE_ROOT.parents[1]
"""Корень репозитория: каталог сервиса лежит на два уровня глубже."""

_REPO_ROOT_MARKER = "services/attribute_extractor/"


def resolve_artifact_path(path: str | Path) -> Path:
    """Разрешить путь артефакта: CWD → корень сервиса → корень репозитория.

    Порядок разрешения:
    1. как задано (CWD процесса); абсолютный путь возвращается как есть;
    2. префикс ``services/attribute_extractor/`` снимается и путь берётся от
       корня сервиса;
    3. относительный путь берётся от корня сервиса, затем от корня
       репозитория (каноническое место генерируемых артефактов — ``data/``,
    4. если ничего не существует — возвращается исходный путь, и решение о
       graceful-деградации принимается на месте вызова.
    """
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    if candidate.is_file() or candidate.is_dir():
        return candidate
    text = candidate.as_posix()
    if _REPO_ROOT_MARKER in text:
        suffix = text.split(_REPO_ROOT_MARKER, 1)[1]
        local = SERVICE_ROOT / suffix
        if local.is_file() or local.is_dir():
            return local
    for base in (SERVICE_ROOT, REPO_ROOT):
        local = base / candidate
        if local.is_file() or local.is_dir():
            return local
    return candidate

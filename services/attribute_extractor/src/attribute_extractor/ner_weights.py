"""Проверка целостности весов NER-модели (каталог модели хранится в Git LFS).

Веса модели (~713 МБ) лежат в репозитории через Git LFS: если их не
подтянуть (``git lfs pull``), на месте файлов окажутся текстовые указатели —
и модель не загрузится ни в docker-образе, ни при локальном запуске.

Модуль даёт одну проверку для двух точек: runtime-деградация сервиса
(``extractors``) и сборка docker-образа (``scripts/check_ner_model.py``).
"""

from __future__ import annotations

from pathlib import Path

from attribute_extractor.constants import (
    GIT_LFS_POINTER_HEAD_BYTES,
    GIT_LFS_POINTER_PREFIX,
    NER_CONFIG_FILENAME,
    NER_TOKENIZER_FILENAME,
    NER_WEIGHTS_FILENAME,
)

NER_REQUIRED_FILES = (NER_CONFIG_FILENAME, NER_TOKENIZER_FILENAME, NER_WEIGHTS_FILENAME)
"""Файлы, без которых каталог модели нельзя загрузить."""


def is_git_lfs_pointer(path: Path) -> bool:
    """Файл является указателем Git LFS, а не реальными данными.

    Нечитаемый файл указателем не считается: проблема с правами доступа —
    это другая диагностика, её даст загрузка модели.
    """
    try:
        with path.open("rb") as handle:
            head = handle.read(GIT_LFS_POINTER_HEAD_BYTES)
    except OSError:
        return False
    return head.startswith(GIT_LFS_POINTER_PREFIX)


def find_lfs_pointers(model_dir: Path) -> list[Path]:
    """Файлы-указатели Git LFS верхнего уровня каталога модели."""
    if not model_dir.is_dir():
        return []
    return sorted(
        path for path in model_dir.iterdir() if path.is_file() and is_git_lfs_pointer(path)
    )


def check_model_dir(model_dir: Path) -> list[str]:
    """Проблемы каталога модели; пустой список — каталог готов к загрузке."""
    if not model_dir.is_dir():
        return [f"каталог модели не найден: {model_dir}"]

    problems: list[str] = []
    for name in NER_REQUIRED_FILES:
        if not (model_dir / name).is_file():
            problems.append(f"нет обязательного файла модели: {name}")

    pointer_problem = lfs_pointer_problem(model_dir)
    if pointer_problem is not None:
        problems.append(pointer_problem)
    return problems


def lfs_pointer_problem(model_dir: Path) -> str | None:
    """Причина «веса не скачаны» или ``None``, если указателей Git LFS нет.

    Runtime-проверка: каталог с указателями LFS заведомо не загрузится, поэтому
    сервис сообщает точную причину вместо traceback'а загрузчика модели.
    """
    pointers = find_lfs_pointers(model_dir)
    if not pointers:
        return None
    names = ", ".join(path.name for path in pointers)
    return f"файлы модели — указатели Git LFS ({names}): выполните `git lfs pull`"

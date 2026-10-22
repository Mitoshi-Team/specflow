"""Тесты проверки целостности весов NER-модели (Git LFS) и выбора устройства.

Модель не загружается: проверяются файловые проверки каталога весов и
логика выбора устройства инференса.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from attribute_extractor.constants import (
    DEFAULT_NER_DEVICE,
    GIT_LFS_POINTER_PREFIX,
    NER_CONFIG_FILENAME,
    NER_DEVICE_AUTO,
    NER_DEVICE_CPU,
    NER_DEVICE_CUDA,
    NER_TOKENIZER_FILENAME,
    NER_WEIGHTS_FILENAME,
)
from attribute_extractor.ner_model import TransformersSpanPredictor
from attribute_extractor.ner_weights import (
    check_model_dir,
    find_lfs_pointers,
    is_git_lfs_pointer,
)

_LFS_POINTER = (
    GIT_LFS_POINTER_PREFIX
    + b"\noid sha256:0000000000000000000000000000000000000000000000000000000000000000\n"
    + b"size 709090132\n"
)


def _write_model_dir(root: Path, *, lfs: bool = False) -> Path:
    """Каталог модели с обязательными файлами (опционально — указатели LFS)."""
    model_dir = root / "ner"
    model_dir.mkdir()
    for name, payload in (
        (NER_CONFIG_FILENAME, b"{}"),
        (NER_TOKENIZER_FILENAME, b"{}"),
        (NER_WEIGHTS_FILENAME, b"weights"),
    ):
        (model_dir / name).write_bytes(_LFS_POINTER if lfs else payload)
    return model_dir


def test_is_git_lfs_pointer_detects_pointer(tmp_path: Path) -> None:
    path = tmp_path / "model.safetensors"
    path.write_bytes(_LFS_POINTER)

    assert is_git_lfs_pointer(path) is True


def test_is_git_lfs_pointer_false_for_real_weights(tmp_path: Path) -> None:
    path = tmp_path / "model.safetensors"
    path.write_bytes(b"\x00\x01real-weights")

    assert is_git_lfs_pointer(path) is False


def test_is_git_lfs_pointer_false_for_missing_file(tmp_path: Path) -> None:
    assert is_git_lfs_pointer(tmp_path / "нет-файла") is False


def test_find_lfs_pointers_lists_only_pointers(tmp_path: Path) -> None:
    model_dir = _write_model_dir(tmp_path)
    (model_dir / NER_WEIGHTS_FILENAME).write_bytes(_LFS_POINTER)

    pointers = find_lfs_pointers(model_dir)

    assert [path.name for path in pointers] == [NER_WEIGHTS_FILENAME]


def test_find_lfs_pointers_for_missing_dir(tmp_path: Path) -> None:
    assert find_lfs_pointers(tmp_path / "нет-каталога") == []


def test_check_model_dir_reports_missing_directory(tmp_path: Path) -> None:
    problems = check_model_dir(tmp_path / "нет-каталога")

    assert problems
    assert "не найден" in problems[0]


def test_check_model_dir_reports_missing_required_files(tmp_path: Path) -> None:
    model_dir = tmp_path / "ner"
    model_dir.mkdir()

    problems = check_model_dir(model_dir)

    assert len(problems) == 3
    assert any(NER_CONFIG_FILENAME in problem for problem in problems)
    assert any(NER_TOKENIZER_FILENAME in problem for problem in problems)
    assert any(NER_WEIGHTS_FILENAME in problem for problem in problems)


def test_check_model_dir_reports_lfs_pointers(tmp_path: Path) -> None:
    model_dir = _write_model_dir(tmp_path, lfs=True)

    problems = check_model_dir(model_dir)

    assert any("git lfs pull" in problem for problem in problems)


def test_check_model_dir_accepts_complete_model(tmp_path: Path) -> None:
    model_dir = _write_model_dir(tmp_path)

    assert check_model_dir(model_dir) == []


def _predictor_with_cuda(available: bool) -> TransformersSpanPredictor:
    """Предиктор без загрузки модели: подменён только признак доступности CUDA."""
    predictor = TransformersSpanPredictor.__new__(TransformersSpanPredictor)
    predictor._torch = SimpleNamespace(
        cuda=SimpleNamespace(is_available=lambda: available),
    )
    return predictor


@pytest.mark.parametrize(
    ("device", "cuda_available", "expected"),
    [
        (None, False, NER_DEVICE_CPU),
        (None, True, NER_DEVICE_CUDA),
        (NER_DEVICE_AUTO, False, NER_DEVICE_CPU),
        (NER_DEVICE_AUTO, True, NER_DEVICE_CUDA),
        (NER_DEVICE_CPU, True, NER_DEVICE_CPU),
        # Запрошенный cuda без GPU — штатная деградация до CPU, не ошибка.
        (NER_DEVICE_CUDA, False, NER_DEVICE_CPU),
        (NER_DEVICE_CUDA, True, NER_DEVICE_CUDA),
    ],
)
def test_resolve_device(device: str | None, cuda_available: bool, expected: str) -> None:
    predictor = _predictor_with_cuda(cuda_available)

    assert predictor._resolve_device(device) == expected


def _load_check_script():
    """Загрузить скрипт проверки весов как модуль (путь в src добавляет он сам)."""
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_ner_model.py"
    spec = importlib.util.spec_from_file_location("check_ner_model", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_check_script_returns_zero_for_ready_model(tmp_path: Path, capsys) -> None:
    model_dir = _write_model_dir(tmp_path)
    module = _load_check_script()

    assert module.main([str(model_dir)]) == 0
    assert "готов" in capsys.readouterr().out


def test_check_script_returns_one_for_broken_model(tmp_path: Path, capsys) -> None:
    model_dir = _write_model_dir(tmp_path, lfs=True)
    module = _load_check_script()

    assert module.main([str(model_dir)]) == 1
    assert "git lfs pull" in capsys.readouterr().err


def test_default_ner_device_is_auto() -> None:
    assert DEFAULT_NER_DEVICE == NER_DEVICE_AUTO

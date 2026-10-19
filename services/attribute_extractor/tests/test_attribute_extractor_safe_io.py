"""Безопасная десериализация pickle-файлов данных (safe_io).

Регрессия безопасности: ``pickle.load`` исполняет код из файла; ограниченный
unpickler обязан отклонять любые объекты с классами до их исполнения.
"""

from __future__ import annotations

import io
import pickle
from pathlib import Path

import pytest

from attribute_extractor.safe_io import (
    RestrictedUnpickler,
    load_pickle_file,
    restricted_pickle_load,
)


class _Widget:
    """Тестовый объект: его десериализация требует импорта класса."""

    def __init__(self) -> None:
        self.value = 1


def _touch(path: str) -> None:
    """Создаёт файл — аналог вредоносного действия payload'а при исполнении."""
    Path(path).touch()


class _Exploit:
    """Payload, при десериализации создающий файл (модель атаки через __reduce__)."""

    def __init__(self, marker: Path) -> None:
        self._marker = marker

    def __reduce__(self):  # type: ignore[no-untyped-def]
        # При исполнении вызвался бы _touch — как os.system в реальной атаке.
        return (_touch, (str(self._marker),))


def test_loads_plain_data_types() -> None:
    """Чистые данные (dict/list/str/числа) десериализуются без ограничений по значению."""
    payload = {
        "yml_catalog": {
            "shop": {
                "categories": {"category": [{"@id": "1", "#text": "Смартфоны"}]},
                "offers": {"offer": [{"@id": "sku-1", "param": [1, 2.5, None, True]}]},
            }
        }
    }

    result = restricted_pickle_load(io.BytesIO(pickle.dumps(payload)))

    assert result == payload


def test_load_pickle_file_reads_from_disk(tmp_path: Path) -> None:
    """``load_pickle_file`` читает файл с диска через ограниченный unpickler."""
    path = tmp_path / "data.pkl"
    path.write_bytes(pickle.dumps(["a", {"b": 2}]))

    assert load_pickle_file(path) == ["a", {"b": 2}]


def test_rejects_class_instance() -> None:
    """Объект пользовательского класса отклоняется: find_class запрещён."""
    payload = io.BytesIO(pickle.dumps(_Widget()))

    with pytest.raises(pickle.UnpicklingError, match="запрещён"):
        restricted_pickle_load(payload)


def test_rejects_reduce_payload_without_execution(tmp_path: Path) -> None:
    """RCE-регрессия: payload с __reduce__ не исполняется, а отклоняется."""
    marker = tmp_path / "pwned"
    payload = io.BytesIO(pickle.dumps(_Exploit(marker)))

    with pytest.raises(pickle.UnpicklingError, match="запрещён"):
        restricted_pickle_load(payload)

    assert not marker.exists(), "payload не должен был исполниться"


def test_rejects_corrupt_data() -> None:
    """Битые данные дают UnpicklingError, а не полумолчаливое поведение."""
    with pytest.raises(pickle.UnpicklingError):
        restricted_pickle_load(io.BytesIO(b"not a pickle"))


def test_restricted_unpickler_is_pickle_unpickler() -> None:
    """Ограниченный загрузчик сохраняет совместимость с интерфейсом pickle."""
    assert issubclass(RestrictedUnpickler, pickle.Unpickler)

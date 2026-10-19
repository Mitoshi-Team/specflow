"""Безопасная десериализация файлов данных.

``pickle.load`` выполняет любой код, зашитый в файл: подменённый или
полученный из недоверенного источника ``skus.pkl`` даёт произвольное
выполнение команд (arbitrary code execution). Каталог YML — чистые данные
(dict/list/str/числа), которым не нужны импортируемые классы, поэтому
десериализация разрешена только для встроенных типов; любая попытка
импортировать класс отклоняется ``RestrictedUnpickler``.
"""

import pickle
from pathlib import Path
from typing import Any, BinaryIO


class RestrictedUnpickler(pickle.Unpickler):
    """Unpickler, запрещающий импорт любых классов при десериализации."""

    def find_class(self, module: str, name: str) -> Any:
        # Каталог YML распадается на встроенные типы, поэтому find_class
        # не должен вызываться вовсе; иначе — отказ (защита от RCE).
        raise pickle.UnpicklingError(f"Импорт классов при десериализации запрещён: {module}.{name}")


def restricted_pickle_load(source: BinaryIO) -> Any:
    """Десериализует pickle из бинарного потока, разрешая только встроенные типы.

    Ошибка формата или попытка загрузки объекта с классом поднимают
    ``pickle.UnpicklingError`` с внятным описанием — вызывающий код
    сообщает о недоверенном/битом файле, а не исполняет его содержимое.
    """
    return RestrictedUnpickler(source).load()


def load_pickle_file(path: Path | str) -> Any:
    """Читает pickle-файл данных через ограниченный unpickler (см. ``restricted_pickle_load``)."""
    with Path(path).open("rb") as source:
        return restricted_pickle_load(source)

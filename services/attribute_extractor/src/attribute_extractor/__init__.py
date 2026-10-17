"""Пакет сервиса извлечения атрибутов.

Экспорты ``app``/``create_app`` доступны лениво (PEP 562): импорт пакета не
тянет fastapi и настройки, чтобы библиотечные модули (grounding, gold,
normalization) переиспользовались в скриптах и обучении без веб-стека.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from attribute_extractor.main import app, create_app

__all__ = ["app", "create_app"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from attribute_extractor import main

        return getattr(main, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""Тесты ленивого импорта пакета attribute_extractor."""

from __future__ import annotations

import subprocess
import sys


def test_package_import_does_not_load_web_app() -> None:
    """Импорт пакета не тянет main/fastapi — модули переиспользуются в скриптах."""
    code = "import sys, attribute_extractor; assert 'attribute_extractor.main' not in sys.modules"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_app_and_create_app_are_available() -> None:
    from attribute_extractor import app, create_app

    assert callable(create_app)
    assert app is not None

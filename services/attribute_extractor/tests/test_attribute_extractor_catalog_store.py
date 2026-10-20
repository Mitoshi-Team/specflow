"""Тесты CatalogStore: загрузка каталога/блоклиста не подавляет сбои молча.

Регрессия к хакатон-ревью: раньше широкий ``except Exception: pass``
возвращал пустой каталог/блоклист без единого слова в лог — порча файла
проходила незаметно, а ``save_catalog`` затирал данные пустым дефолтом.
"""

from __future__ import annotations

import logging

from attribute_extractor.catalog_store import CatalogStore
from attribute_extractor.field_catalog_seed import FIELD_CATALOG_VERSION


def _messages(caplog) -> list[str]:
    return [record.getMessage() for record in caplog.records]


def test_load_catalog_missing_file_returns_default_without_error_log(tmp_path, caplog):
    """Отсутствие файла — штатный первый запуск, не ошибка."""
    store = CatalogStore(tmp_path / "cat.json", tmp_path / "bl.txt")
    with caplog.at_level(logging.ERROR, logger="attribute_extractor.catalog_store"):
        assert store.load_catalog() == {"version": FIELD_CATALOG_VERSION, "entries": []}
    assert caplog.records == []


def test_load_catalog_corrupt_json_returns_default_and_logs(tmp_path, caplog):
    """Битый JSON деградирует пустым каталогом, но с ERROR-логом с путём."""
    path = tmp_path / "cat.json"
    path.write_text("{не json", encoding="utf-8")
    store = CatalogStore(path, tmp_path / "bl.txt")
    with caplog.at_level(logging.ERROR, logger="attribute_extractor.catalog_store"):
        assert store.load_catalog() == {"version": FIELD_CATALOG_VERSION, "entries": []}
    assert any(str(path) in message for message in _messages(caplog))


def test_load_catalog_unreadable_file_returns_default_and_logs(tmp_path, caplog):
    """Нечитаемый путь (каталог вместо файла) → OSError читается в лог."""
    path = tmp_path / "cat.json"
    path.mkdir()  # open() над каталогом даёт IsADirectoryError (OSError)
    store = CatalogStore(path, tmp_path / "bl.txt")
    with caplog.at_level(logging.ERROR, logger="attribute_extractor.catalog_store"):
        assert store.load_catalog() == {"version": FIELD_CATALOG_VERSION, "entries": []}
    assert any(str(path) in message for message in _messages(caplog))


def test_load_catalog_non_dict_payload_returns_default_and_logs(tmp_path, caplog):
    """Корректный JSON неожиданной формы не роняет вызывающий код молча."""
    path = tmp_path / "cat.json"
    path.write_text("[]", encoding="utf-8")
    store = CatalogStore(path, tmp_path / "bl.txt")
    with caplog.at_level(logging.ERROR, logger="attribute_extractor.catalog_store"):
        assert store.load_catalog() == {"version": FIELD_CATALOG_VERSION, "entries": []}
    assert any(str(path) in message for message in _messages(caplog))


def test_load_blocklist_unreadable_file_returns_empty_and_logs(tmp_path, caplog):
    """Нечитаемый блоклист деградирует пустым списком с ERROR-логом."""
    path = tmp_path / "bl.txt"
    path.mkdir()
    store = CatalogStore(tmp_path / "cat.json", path)
    with caplog.at_level(logging.ERROR, logger="attribute_extractor.catalog_store"):
        assert store.load_blocklist() == []
    assert any(str(path) in message for message in _messages(caplog))


def test_save_then_load_catalog_roundtrip(tmp_path):
    """Штатный сценарий не задет логикой деградации."""
    store = CatalogStore(tmp_path / "cat.json", tmp_path / "bl.txt")
    payload = {"version": FIELD_CATALOG_VERSION, "entries": [{"code": "ram"}]}
    store.save_catalog(payload)
    assert store.load_catalog() == payload

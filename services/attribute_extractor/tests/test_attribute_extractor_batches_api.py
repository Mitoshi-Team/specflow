"""Серверная история батчей: POST сохраняет, GET /batches отдаёт (api_contract.md, 4.8/4.9).

Проверяется гарантия ревью: батчи персистентны на сервере, сбой хранилища
виден клиенту (persisted=false либо 503 ErrorResponse с логом), а не
подавляется молча.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi.testclient import TestClient

from attribute_extractor.batch_store import (
    BatchStoreError,
    InMemoryBatchStore,
    PostgresBatchStore,
)
from attribute_extractor.config import settings
from attribute_extractor.constants import (
    BATCH_LIST_MAX_LIMIT,
    BATCHES_ENDPOINT,
    EXTRACT_BATCH_ENDPOINT,
)
from attribute_extractor.main import app, create_app

CLEAN_TITLE = "Смартфон realme C33 4/128GB Gold"


def _path(endpoint: str) -> str:
    return f"{settings.api_prefix}{endpoint}"


def _assert_error_envelope(body: dict[str, Any], *, code: str) -> None:
    assert isinstance(body["detail"], str) and body["detail"]
    assert body["code"] == code


class _FailingStore:
    """Заглушка сломанного хранилища: каждая операция падает с BatchStoreError."""

    def save(self, batch: Any) -> None:
        raise BatchStoreError("запись недоступна")

    def list_batches(self, limit: int, offset: int) -> tuple[list[Any], int]:
        raise BatchStoreError("чтение недоступно")

    def get_batch(self, batch_id: str) -> None:
        raise BatchStoreError("чтение недоступно")


# --- Выбор режима хранилища ---------------------------------------------------


def test_uses_in_memory_store_when_database_url_unset() -> None:
    """Без EXTRACTOR_DATABASE_URL — память процесса (dev без БД), без сети."""
    built = create_app()

    assert isinstance(built.state.batch_store, InMemoryBatchStore)


def test_uses_postgres_store_when_database_url_set(monkeypatch) -> None:
    """EXTRACTOR_DATABASE_URL включает PostgreSQL; подключение ленивое."""
    monkeypatch.setenv("EXTRACTOR_DATABASE_URL", "postgresql://u:p@127.0.0.1:9/x")

    built = create_app()

    assert isinstance(built.state.batch_store, PostgresBatchStore)


# --- POST /extract/batch → запись в историю -----------------------------------


def test_extract_batch_persists_and_is_gettable() -> None:
    """Успешный батч попадает в историю: сводка в списке, полный батч по id."""
    with TestClient(create_app()) as client:
        posted = client.post(
            _path(EXTRACT_BATCH_ENDPOINT),
            json={"items": [{"title": CLEAN_TITLE}], "threshold_override": 0.95},
        )

        batch_id = posted.json()["batch_id"]
        assert posted.json()["persisted"] is True
        assert batch_id

        listing = client.get(_path(BATCHES_ENDPOINT))
        detail = client.get(f"{_path(BATCHES_ENDPOINT)}/{batch_id}")

    assert listing.status_code == 200
    summary = next(item for item in listing.json()["items"] if item["batch_id"] == batch_id)
    assert summary["total"] == posted.json()["total"]
    assert summary["ok"] == posted.json()["ok"]
    assert summary["threshold"] == 0.95
    assert isinstance(summary["created_at"], str)

    assert detail.status_code == 200
    stored = detail.json()
    assert stored["batch_id"] == batch_id
    assert stored["response"]["total"] == posted.json()["total"]
    assert stored["response"]["persisted"] is True
    assert [card["title"] for card in stored["cards"]] == [CLEAN_TITLE]
    assert stored["threshold"] == 0.95


def test_extract_batch_echoes_client_batch_id() -> None:
    """Клиентский batch_id сохраняется и подставляется в ответ (идемпотентность)."""
    with TestClient(create_app()) as client:
        posted = client.post(
            _path(EXTRACT_BATCH_ENDPOINT),
            json={"items": [{"title": CLEAN_TITLE}], "batch_id": "client-b-1"},
        )
        detail = client.get(f"{_path(BATCHES_ENDPOINT)}/client-b-1")

    assert posted.json()["batch_id"] == "client-b-1"
    assert detail.status_code == 200


def test_history_keeps_multiple_batches_newest_first() -> None:
    """Список истории — новые первыми, пагинация limit/offset работает."""
    with TestClient(create_app()) as client:
        for index in range(3):
            client.post(
                _path(EXTRACT_BATCH_ENDPOINT),
                json={"items": [{"title": CLEAN_TITLE}], "batch_id": f"b-{index}"},
            )

        page = client.get(_path(BATCHES_ENDPOINT), params={"limit": 2, "offset": 0})
        tail = client.get(_path(BATCHES_ENDPOINT), params={"limit": 2, "offset": 2})

    assert [item["batch_id"] for item in page.json()["items"]] == ["b-2", "b-1"]
    assert page.json()["total"] == 3
    assert [item["batch_id"] for item in tail.json()["items"]] == ["b-0"]


# --- Ответы об ошибках --------------------------------------------------------


def test_unknown_batch_returns_404_envelope() -> None:
    """Неизвестный batch_id → 404 ErrorResponse (не пустой объект)."""
    with TestClient(create_app()) as client:
        response = client.get(f"{_path(BATCHES_ENDPOINT)}/missing-id")

    assert response.status_code == 404
    _assert_error_envelope(response.json(), code="not_found")
    assert "missing-id" in response.json()["detail"]


def test_batches_list_rejects_invalid_pagination() -> None:
    """limit/offset вне допуска → 422 validation_error (границы контракта)."""
    with TestClient(create_app()) as client:
        too_small = client.get(_path(BATCHES_ENDPOINT), params={"limit": 0})
        too_large = client.get(_path(BATCHES_ENDPOINT), params={"limit": BATCH_LIST_MAX_LIMIT + 1})
        negative_offset = client.get(_path(BATCHES_ENDPOINT), params={"offset": -1})

    for response in (too_small, too_large, negative_offset):
        assert response.status_code == 422
        _assert_error_envelope(response.json(), code="validation_error")


def test_store_save_failure_returns_persisted_false_and_logs(caplog) -> None:
    """Сбой записи в БД: извлечение отвечает 200 с persisted=false + ERROR-лог.

    Гарантия ревью: ошибка записи видна (лог с traceback, признак в ответе),
    а не подавляется молча; при этом сбой истории не роняет обработку.
    """
    broken_app = create_app()
    broken_app.state.batch_store = _FailingStore()

    with caplog.at_level(logging.ERROR, logger="attribute_extractor.main"):
        with TestClient(broken_app) as client:
            response = client.post(
                _path(EXTRACT_BATCH_ENDPOINT), json={"items": [{"title": CLEAN_TITLE}]}
            )

    assert response.status_code == 200
    assert response.json()["persisted"] is False
    assert response.json()["total"] == 1
    error_logs = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert error_logs, "сбой записи должен логироваться на уровне ERROR"
    assert any(response.json()["batch_id"] in record.getMessage() for record in error_logs)


def test_store_read_failure_returns_503_envelope_and_logs(caplog) -> None:
    """Сбой чтения истории → 503 ErrorResponse с логом, а не пустой список."""
    broken_app = create_app()
    broken_app.state.batch_store = _FailingStore()

    with caplog.at_level(logging.ERROR, logger="attribute_extractor.main"):
        with TestClient(broken_app) as client:
            listing = client.get(_path(BATCHES_ENDPOINT))
            detail = client.get(f"{_path(BATCHES_ENDPOINT)}/any-id")

    for response in (listing, detail):
        assert response.status_code == 503
        _assert_error_envelope(response.json(), code="http_error")
    error_logs = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert len(error_logs) >= 2, "оба сбоя чтения должны фиксироваться в логе"


# --- OpenAPI ------------------------------------------------------------------


def test_openapi_documents_batch_history_errors() -> None:
    """404/503 новых эндпоинтов описаны в OpenAPI как ErrorResponse."""
    with TestClient(app) as client:
        paths = client.get("/openapi.json").json()["paths"]

    list_op = paths[_path(BATCHES_ENDPOINT)]["get"]
    detail_op = paths[f"{_path(BATCHES_ENDPOINT)}/{{batch_id}}"]["get"]
    error_ref = {"$ref": "#/components/schemas/ErrorResponse"}

    assert list_op["responses"]["503"]["content"]["application/json"]["schema"] == error_ref
    assert detail_op["responses"]["404"]["content"]["application/json"]["schema"] == error_ref
    assert detail_op["responses"]["503"]["content"]["application/json"]["schema"] == error_ref

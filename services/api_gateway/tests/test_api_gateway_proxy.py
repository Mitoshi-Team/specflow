"""Unit-тесты проксирования публичных маршрутов шлюза в сервис извлечения.

Upstream подменяется ``httpx.MockTransport``: реальный сетевой сервис в
unit-тестах не используется (AGENTS.md, раздел «Тесты»).
"""

from collections.abc import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from api_gateway.constants import (
    API_PREFIX,
    PROXY_ACCEPT_ENCODING,
    UPSTREAM_UNAVAILABLE_DETAIL,
)
from api_gateway.main import create_app

_BATCH_PATH = f"{API_PREFIX}/extract/batch"


def _build_client(handler: Callable[[httpx.Request], httpx.Response]) -> TestClient:
    """TestClient шлюза с подменённым транспортом upstream."""
    app = create_app(upstream_transport=httpx.MockTransport(handler))
    return TestClient(app)


def test_batch_request_is_forwarded_to_extractor() -> None:
    seen: dict[str, str | bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(
            method=request.method,
            url=str(request.url),
            body=request.content,
            content_type=request.headers.get("content-type", ""),
            accept_encoding=request.headers.get("accept-encoding", ""),
        )
        return httpx.Response(200, json={"total": 1, "results": []})

    with _build_client(handler) as client:
        response = client.post(_BATCH_PATH, json={"items": [{"title": "телефон"}]})

    assert response.status_code == 200
    assert response.json() == {"total": 1, "results": []}
    assert seen["method"] == "POST"
    assert str(seen["url"]).endswith(_BATCH_PATH)
    assert seen["content_type"] == "application/json"
    assert b'"title"' in bytes(seen["body"])
    # Сжатие отключено, чтобы шлюз не переупаковывал тело.
    assert seen["accept_encoding"] == PROXY_ACCEPT_ENCODING


def test_upstream_error_status_and_body_are_passed_through() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={"detail": "ошибка", "code": "validation_error", "errors": []},
        )

    with _build_client(handler) as client:
        response = client.post(_BATCH_PATH, json={"items": []})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["detail"] == "ошибка"


def test_query_params_are_forwarded() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"items": [], "total": 0})

    with _build_client(handler) as client:
        response = client.get(f"{API_PREFIX}/categories", params={"category": "phone", "limit": 10})

    assert response.status_code == 200
    assert "category=phone" in seen["url"]
    assert "limit=10" in seen["url"]


def test_get_info_is_forwarded() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(200, json={"service_name": "attribute-extractor"})

    with _build_client(handler) as client:
        response = client.get(f"{API_PREFIX}/info")

    assert response.status_code == 200
    assert response.json() == {"service_name": "attribute-extractor"}


def test_health_is_served_locally_without_upstream() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("локальный /health не должен проксироваться в upstream")

    with _build_client(handler) as client:
        response = client.get(f"{API_PREFIX}/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unreachable_upstream_returns_bad_gateway() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with _build_client(handler) as client:
        response = client.post(_BATCH_PATH, json={"items": [{"title": "x"}]})

    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "http_error"
    assert body["detail"] == UPSTREAM_UNAVAILABLE_DETAIL


def test_hop_by_hop_response_headers_are_stripped() -> None:
    # Заголовки hop-by-hop от upstream не должны утекать клиенту, а длина тела
    # пересчитывается по фактическому содержимому.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"ok": True},
            headers={"connection": "close", "transfer-encoding": "chunked"},
        )

    with _build_client(handler) as client:
        response = client.get(f"{API_PREFIX}/info")

    assert response.status_code == 200
    assert "transfer-encoding" not in response.headers
    assert response.headers["content-length"] == str(len(response.content))

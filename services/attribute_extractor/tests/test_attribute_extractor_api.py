"""HTTP API сервиса: extract, batch, categories, info, config (задача 1).

Форма ответов сверяется с openspec/specs/api_contract.md; карточки берутся из
gold/gold.jsonl. Нарушение инварианта очистки и падение пайплайна
воспроизводятся подстановками — внешние сервисы не используются.
"""

from __future__ import annotations

import json
from pathlib import Path as FsPath
from typing import Any

from fastapi.testclient import TestClient

from attribute_extractor import preprocessing
from attribute_extractor.config import settings
from attribute_extractor.constants import (
    CATEGORIES_ENDPOINT,
    CATEGORY_LIST_MAX_LIMIT,
    CONFIG_ENDPOINT,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_DETERMINISTIC_CONFIDENCE,
    EXTRACT_BATCH_ENDPOINT,
    EXTRACT_ENDPOINT,
    INFO_ENDPOINT,
    NER_EXTRACTOR_NAME,
    RULE_EXTRACTOR_NAME,
)
from attribute_extractor.main import app
from attribute_extractor.pipeline import ExtractPipeline

GOLD_PATH = FsPath(__file__).resolve().parents[1] / "gold" / "gold.jsonl"
GOLD_RECORDS = [json.loads(line) for line in GOLD_PATH.read_text(encoding="utf-8").splitlines()[:2]]

# Карточка с детерминированными rule-кандидатами (confidence=0.9) без
# конфликтов: baseline needs_review=False, override порога меняет статус.
CLEAN_TITLE = "Смартфон realme C33 4/128GB Gold"


def _path(endpoint: str) -> str:
    return f"{settings.api_prefix}{endpoint}"


def _card_body(record: dict[str, Any]) -> dict[str, Any]:
    """Тело запроса ProductCardRequest из gold-записи."""
    data = record["card"]
    return {
        "product_id": data["sku_id"],
        "title": data["title"],
        "description": data["description"],
        "category_id": data["category_id"],
        "category_name": data["category_name"],
    }


# --- POST /extract -----------------------------------------------------------


def test_extract_returns_gold_card_result() -> None:
    """Одиночное извлечение: 200 и форма ExtractionResponseItem."""
    with TestClient(app) as client:
        response = client.post(_path(EXTRACT_ENDPOINT), json=_card_body(GOLD_RECORDS[0]))

    assert response.status_code == 200
    body = response.json()
    assert body["product_id"] == GOLD_RECORDS[0]["card"]["sku_id"]
    assert body["status"] in {"ok", "low_confidence", "partial"}
    assert body["pipeline_version"] == settings.pipeline_version
    assert body["processing_time_ms"] >= 0
    assert body["attributes"], "по gold-карточке ожидаются кандидаты"
    for candidate in body["attributes"]:
        assert candidate["is_confirmed_in_text"] is True
        assert candidate["source_spans"]
        for span in candidate["source_spans"]:
            assert span["field"] in {"title", "description"}


def test_extract_returns_500_on_cleaning_invariant_violation(
    monkeypatch,
) -> None:
    """Нарушение инварианта очистки (Этап 0) → 500 с телом ErrorResponse."""
    monkeypatch.setattr(
        preprocessing,
        "cleaning_invariant_violations",
        lambda *args, **kwargs: ["значение потеряно при очистке: '6.7'"],
    )
    with TestClient(app) as client:
        response = client.post(_path(EXTRACT_ENDPOINT), json={"title": "Экран 6.7 дюйма"})

    assert response.status_code == 500
    body = response.json()
    assert isinstance(body["detail"], str) and body["detail"]


def test_extract_skips_card_without_text() -> None:
    """Карточка только с seller_attributes проходит валидацию и даёт skipped."""
    with TestClient(app) as client:
        response = client.post(
            _path(EXTRACT_ENDPOINT),
            json={"seller_attributes": {"Цвет": "черный"}},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "skipped"
    assert body["attributes"] == []
    assert body["needs_review"] is False


def test_extract_unexpected_pipeline_error_returns_500(monkeypatch) -> None:
    """ValueError, вылетевший из пайплайна, — 500 ErrorResponse, а не traceback."""

    def boom(self, card, **kwargs):
        raise ValueError("некорректные данные пайплайна")

    monkeypatch.setattr(ExtractPipeline, "extract", boom)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(_path(EXTRACT_ENDPOINT), json={"title": "Экран 6.7 дюйма"})

    assert response.status_code == 500
    body = response.json()
    assert isinstance(body["detail"], str) and body["detail"]


# --- POST /extract/batch -----------------------------------------------------


def test_extract_batch_partial_success(monkeypatch) -> None:
    """Битая карточка даёт status=error и не прерывает остальные (сводка верна)."""
    original = ExtractPipeline.extract

    def selective(self, card, **kwargs):
        if card.product_id == "broken":
            raise ValueError("битая карточка")
        return original(self, card, **kwargs)

    monkeypatch.setattr(ExtractPipeline, "extract", selective)
    items = [
        _card_body(GOLD_RECORDS[0]),
        _card_body(GOLD_RECORDS[1]),
        {"product_id": "broken", "title": "Экран 6.7 дюйма"},
    ]
    with TestClient(app) as client:
        response = client.post(
            _path(EXTRACT_BATCH_ENDPOINT),
            json={"items": items, "batch_id": "b-1"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["batch_id"] == "b-1"
    assert body["total"] == 3
    assert body["errors"] == 1
    assert isinstance(body["processing_time_ms_total"], int)
    assert body["processing_time_ms_total"] >= 0
    statuses = [result["status"] for result in body["results"]]
    assert statuses[0] != "error"
    assert statuses[1] != "error"
    assert statuses[2] == "error"
    assert body["ok"] == statuses.count("ok")
    assert body["low_confidence"] == statuses.count("low_confidence")


def test_extract_batch_threshold_override_changes_review() -> None:
    """threshold_override меняет needs_review/low_confidence_count только в батче."""
    items = [{"product_id": "clean", "title": CLEAN_TITLE}]
    with TestClient(app) as client:
        baseline = client.post(_path(EXTRACT_BATCH_ENDPOINT), json={"items": items})
        overridden = client.post(
            _path(EXTRACT_BATCH_ENDPOINT),
            json={"items": items, "threshold_override": 0.95},
        )

    baseline_result = baseline.json()["results"][0]
    overridden_result = overridden.json()["results"][0]
    assert baseline_result["needs_review"] is False
    assert baseline_result["low_confidence_count"] == 0
    assert overridden_result["needs_review"] is True
    assert overridden_result["low_confidence_count"] > 0
    assert overridden_result["status"] in {"low_confidence", "partial"}
    # Глобальные настройки запрос не мутирует.
    assert settings.default_confidence_threshold == DEFAULT_CONFIDENCE_THRESHOLD


def test_extract_batch_rejects_oversized_batch() -> None:
    """Лимит batch_size (1–50) валидацией контракта → 422 без кода в сервисе."""
    items = [{"title": CLEAN_TITLE}] * (settings.max_batch_size + 1)
    with TestClient(app) as client:
        response = client.post(_path(EXTRACT_BATCH_ENDPOINT), json={"items": items})

    assert response.status_code == 422


# --- GET /categories ---------------------------------------------------------


def test_categories_returns_generic_schema_list() -> None:
    """Список схем: items/total; реестр пуст — отдаётся только generic-схема."""
    with TestClient(app) as client:
        response = client.get(_path(CATEGORIES_ENDPOINT))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total"}
    assert body["total"] == len(body["items"]) == 1
    schema = body["items"][0]
    assert schema["category"] == "generic"
    assert schema["schema_version"]


def test_categories_filter_and_pagination() -> None:
    """Фильтр category и пагинация limit/offset не выдумывают схемы."""
    with TestClient(app) as client:
        matched = client.get(_path(CATEGORIES_ENDPOINT), params={"category": "generic"}).json()
        missing = client.get(_path(CATEGORIES_ENDPOINT), params={"category": "Смартфоны"}).json()
        empty_page = client.get(_path(CATEGORIES_ENDPOINT), params={"limit": 0}).json()

    assert matched["total"] == 1
    assert missing == {"items": [], "total": 0}
    assert empty_page == {"items": [], "total": 1}


def test_categories_rejects_limit_above_maximum() -> None:
    """limit больше максимального (200) → 422."""
    with TestClient(app) as client:
        response = client.get(
            _path(CATEGORIES_ENDPOINT), params={"limit": CATEGORY_LIST_MAX_LIMIT + 1}
        )

    assert response.status_code == 422


def test_category_by_name_returns_schema_or_404() -> None:
    """generic-схема доступна по имени; неизвестная категория → 404 ErrorResponse."""
    with TestClient(app) as client:
        found = client.get(f"{_path(CATEGORIES_ENDPOINT)}/generic")
        missing = client.get(f"{_path(CATEGORIES_ENDPOINT)}/Смартфоны")

    assert found.status_code == 200
    assert found.json()["category"] == "generic"
    assert missing.status_code == 404
    body = missing.json()
    assert isinstance(body["detail"], str) and body["detail"]


# --- GET /info и GET /config -------------------------------------------------


def test_info_matches_specification() -> None:
    """info: имя/версии, методы, пороги, признаки по api_contract.md (4.6)."""
    with TestClient(app) as client:
        response = client.get(_path(INFO_ENDPOINT))

    assert response.status_code == 200
    body = response.json()
    assert body["service_name"] == "attribute-extractor"
    assert body["version"] == settings.service_version
    assert body["pipeline_version"] == settings.pipeline_version
    assert body["extraction_methods"] == [RULE_EXTRACTOR_NAME, NER_EXTRACTOR_NAME]
    assert body["default_threshold"] == DEFAULT_CONFIDENCE_THRESHOLD
    assert body["supports_batch"] is True
    assert body["max_batch_size"] == settings.max_batch_size
    assert body["text_only"] is True
    assert body["features"] == {
        "grounding_required": settings.grounding_required,
        "normalization": settings.normalization_enabled,
        "unit_conversion": settings.unit_conversion_enabled,
        "traffic_weighted_metrics": False,
    }


def test_config_returns_thresholds_without_secrets() -> None:
    """config: только read-only пороги, без секретов (api_contract.md, 4.7)."""
    with TestClient(app) as client:
        response = client.get(_path(CONFIG_ENDPOINT))

    assert response.status_code == 200
    assert response.json() == {
        "confidence_thresholds": {
            "auto": settings.default_confidence_threshold,
            "review": settings.review_confidence_threshold,
        },
        "match_threshold": settings.match_threshold,
        "deterministic_confidence": DEFAULT_DETERMINISTIC_CONFIDENCE,
    }


# --- Инфраструктура: OpenAPI и CORS ------------------------------------------


def test_openapi_docs_are_enabled() -> None:
    """Автодокументация OpenAPI включена по умолчанию (/docs, /redoc)."""
    with TestClient(app) as client:
        docs = client.get("/docs")
        redoc = client.get("/redoc")
        openapi = client.get("/openapi.json")

    assert docs.status_code == 200
    assert redoc.status_code == 200
    assert openapi.status_code == 200


def test_cors_allows_configured_origins() -> None:
    """Разрешённые источники берутся из настроек (EXTRACTOR_CORS_ORIGINS)."""
    origin = settings.cors_origins[0]
    with TestClient(app) as client:
        response = client.options(
            _path(EXTRACT_ENDPOINT),
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin

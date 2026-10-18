"""Верификация /health и деградации без модели (api_contract.md, 3.7, 4.5)."""

from fastapi.testclient import TestClient

from attribute_extractor import config
from attribute_extractor.constants import EXTRACT_ENDPOINT, HEALTH_ENDPOINT
from attribute_extractor.main import create_app
from specflow_contracts.enums import ExtractionStatus, HealthStatus

# Карточка с детерминированными rule-кандидатами (confidence=0.9).
CLEAN_TITLE = "Смартфон realme C33 4/128GB Gold"


def _extract(client: TestClient) -> dict:
    """POST /extract по тестовой карточке; возвращает тело ответа."""
    response = client.post(
        f"{config.settings.api_prefix}{EXTRACT_ENDPOINT}",
        json={"title": CLEAN_TITLE, "description": "", "seller_attributes": []},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_health_stable_when_vector_match_disabled(monkeypatch):
    """Vector-index выключен, NER недоступен → degraded (без фальшивого OK)."""
    monkeypatch.setenv("EXTRACTOR_ENABLE_VECTOR_MATCH", "false")
    with TestClient(create_app()) as client:
        response = client.get(f"{config.settings.api_prefix}{HEALTH_ENDPOINT}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == HealthStatus.DEGRADED.value
    assert payload["version"]
    assert payload["pipeline_version"]
    assert payload["models_loaded"] == ["rules"]
    assert payload["uptime_seconds"] >= 0


def test_health_reports_vector_index_component(monkeypatch):
    """Vector-index включён → компонент vector_index в models_loaded."""
    monkeypatch.setenv("EXTRACTOR_ENABLE_VECTOR_MATCH", "true")
    with TestClient(create_app()) as client:
        response = client.get(f"{config.settings.api_prefix}{HEALTH_ENDPOINT}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == HealthStatus.DEGRADED.value  # NER всё ещё нет
    assert payload["models_loaded"] == ["rules", "vector_index"]


def test_extract_does_not_fail_without_ner(monkeypatch):
    """Деградация (NER/индекс недоступны) не роняет извлечение."""
    monkeypatch.setenv("EXTRACTOR_ENABLE_VECTOR_MATCH", "false")
    with TestClient(create_app()) as client:
        body = _extract(client)

    assert body["status"] == ExtractionStatus.OK.value
    assert body["attributes"]


def test_extract_without_rules_returns_empty_result(monkeypatch):
    """Rules выключены, NER недоступен → пустой результат без ошибки.

    LLM-путь удалён из пайплайна (change rework-extraction-pipeline), поэтому
    карточка получает пустой ok-результат, а не llm_partial.
    """
    monkeypatch.setenv("EXTRACTOR_ENABLE_RULES", "false")
    with TestClient(create_app()) as client:
        body = _extract(client)

    assert body["status"] == ExtractionStatus.OK.value
    assert body["attributes"] == []
    assert body["needs_review"] is False

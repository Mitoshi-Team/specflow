import pytest
from pydantic import ValidationError

from api_gateway.config import Settings
from api_gateway.constants import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_EXTRACTOR_URL,
    DEFAULT_MAX_BATCH_SIZE,
    DEFAULT_PIPELINE_VERSION,
    DEFAULT_UPSTREAM_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_UPSTREAM_TIMEOUT_SECONDS,
    SERVICE_VERSION,
)
from specflow_contracts.constants import MAX_BATCH_SIZE


def test_settings_defaults() -> None:
    config = Settings(_env_file=None)

    assert config.service_version == SERVICE_VERSION
    assert config.pipeline_version == DEFAULT_PIPELINE_VERSION
    assert config.default_confidence_threshold == DEFAULT_CONFIDENCE_THRESHOLD
    assert config.max_batch_size == DEFAULT_MAX_BATCH_SIZE
    assert config.attribute_extractor_url == DEFAULT_EXTRACTOR_URL
    assert config.upstream_timeout_seconds == DEFAULT_UPSTREAM_TIMEOUT_SECONDS
    assert config.upstream_connect_timeout_seconds == DEFAULT_UPSTREAM_CONNECT_TIMEOUT_SECONDS


def test_max_batch_size_matches_api_contract() -> None:
    config = Settings(_env_file=None)

    assert config.max_batch_size == MAX_BATCH_SIZE


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_GATEWAY_ATTRIBUTE_EXTRACTOR_URL", "http://extractor:9999")
    monkeypatch.setenv("API_GATEWAY_UPSTREAM_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("API_GATEWAY_MAX_BATCH_SIZE", "10")
    monkeypatch.setenv("API_GATEWAY_DEFAULT_CONFIDENCE_THRESHOLD", "0.7")

    config = Settings(_env_file=None)

    assert config.attribute_extractor_url == "http://extractor:9999"
    assert config.upstream_timeout_seconds == 12.5
    assert config.max_batch_size == 10
    assert config.default_confidence_threshold == 0.7


def test_rejects_max_batch_size_above_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_GATEWAY_MAX_BATCH_SIZE", str(MAX_BATCH_SIZE + 1))

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_rejects_confidence_threshold_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_GATEWAY_DEFAULT_CONFIDENCE_THRESHOLD", "-0.1")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_rejects_non_positive_upstream_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_GATEWAY_UPSTREAM_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)

import pytest
from pydantic import ValidationError

from attribute_extractor.config import Settings
from attribute_extractor.constants import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_LLM_TIMEOUT_SECONDS,
    DEFAULT_MAX_BATCH_SIZE,
    DEFAULT_METHOD_WEIGHTS,
    DEFAULT_PIPELINE_VERSION,
    DEFAULT_RULES_VERSION,
    DEFAULT_VOCAB_VERSION,
    REVIEW_CONFIDENCE_THRESHOLD,
    SERVICE_VERSION,
)
from specflow_contracts.constants import MAX_BATCH_SIZE


def test_settings_defaults() -> None:
    config = Settings(_env_file=None)

    assert config.service_version == SERVICE_VERSION
    assert config.pipeline_version == DEFAULT_PIPELINE_VERSION
    assert config.rules_version == DEFAULT_RULES_VERSION
    assert config.vocab_version == DEFAULT_VOCAB_VERSION
    assert config.default_confidence_threshold == DEFAULT_CONFIDENCE_THRESHOLD
    assert config.review_confidence_threshold == REVIEW_CONFIDENCE_THRESHOLD
    assert config.max_batch_size == DEFAULT_MAX_BATCH_SIZE
    assert config.method_weights == DEFAULT_METHOD_WEIGHTS
    assert config.llm_timeout_seconds == DEFAULT_LLM_TIMEOUT_SECONDS
    assert config.enable_llm is False
    assert config.grounding_required is True


def test_max_batch_size_matches_api_contract() -> None:
    config = Settings(_env_file=None)

    assert config.max_batch_size == MAX_BATCH_SIZE


def test_method_weights_are_copied_per_instance() -> None:
    first = Settings(_env_file=None)
    first.method_weights["rule"] = 0.1

    second = Settings(_env_file=None)

    assert second.method_weights == DEFAULT_METHOD_WEIGHTS


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTRACTOR_MAX_BATCH_SIZE", "5")
    monkeypatch.setenv("EXTRACTOR_DEFAULT_CONFIDENCE_THRESHOLD", "0.65")
    monkeypatch.setenv("EXTRACTOR_LLM_TIMEOUT_SECONDS", "5.5")
    monkeypatch.setenv("EXTRACTOR_METHOD_WEIGHTS", '{"rule": 0.4, "llm": 0.2}')

    config = Settings(_env_file=None)

    assert config.max_batch_size == 5
    assert config.default_confidence_threshold == 0.65
    assert config.llm_timeout_seconds == 5.5
    assert config.method_weights == {"rule": 0.4, "llm": 0.2}


def test_rejects_method_weight_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTRACTOR_METHOD_WEIGHTS", '{"rule": 1.5}')

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_rejects_threshold_order_violation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTRACTOR_REVIEW_CONFIDENCE_THRESHOLD", "0.9")
    monkeypatch.setenv("EXTRACTOR_DEFAULT_CONFIDENCE_THRESHOLD", "0.5")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_rejects_confidence_threshold_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTRACTOR_DEFAULT_CONFIDENCE_THRESHOLD", "1.5")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)

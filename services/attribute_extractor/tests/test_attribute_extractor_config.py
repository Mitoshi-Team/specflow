import pytest
from pydantic import ValidationError

from attribute_extractor.config import Settings
from attribute_extractor.constants import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_MATCH_THRESHOLD,
    DEFAULT_MAX_BATCH_SIZE,
    DEFAULT_PIPELINE_VERSION,
    DEFAULT_RULES_VERSION,
    DEFAULT_VECTOR_BACKEND,
    DEFAULT_VECTOR_K,
    DEFAULT_VOCAB_VERSION,
    DETERMINISTIC_CONFIDENCE,
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
    assert config.deterministic_confidence == DETERMINISTIC_CONFIDENCE
    assert config.max_batch_size == DEFAULT_MAX_BATCH_SIZE
    assert config.grounding_required is True


def test_max_batch_size_matches_api_contract() -> None:
    config = Settings(_env_file=None)

    assert config.max_batch_size == MAX_BATCH_SIZE


def test_vector_settings_defaults() -> None:
    config = Settings(_env_file=None)

    assert config.vector_backend == DEFAULT_VECTOR_BACKEND
    assert config.embedding_model == DEFAULT_EMBEDDING_MODEL
    assert config.match_threshold == DEFAULT_MATCH_THRESHOLD
    assert config.vector_k == DEFAULT_VECTOR_K


def test_vector_backend_rejects_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTRACTOR_VECTOR_BACKEND", "bogus")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_vector_settings_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTRACTOR_VECTOR_BACKEND", "lexical")
    monkeypatch.setenv("EXTRACTOR_VECTOR_K", "3")

    config = Settings(_env_file=None)

    assert config.vector_backend == "lexical"
    assert config.vector_k == 3


def test_aggregation_settings_absent_per_spec() -> None:
    """Веса методов, гибрид и LLM удалены спекой — настроек не должно быть."""
    config = Settings(_env_file=None)

    assert not hasattr(config, "method_weights")
    assert not hasattr(config, "hybrid_strategy")
    assert not hasattr(config, "enable_llm")


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTRACTOR_MAX_BATCH_SIZE", "5")
    monkeypatch.setenv("EXTRACTOR_DEFAULT_CONFIDENCE_THRESHOLD", "0.65")
    monkeypatch.setenv("EXTRACTOR_DETERMINISTIC_CONFIDENCE", "0.85")
    monkeypatch.setenv("EXTRACTOR_GROUNDING_REQUIRED", "false")

    config = Settings(_env_file=None)

    assert config.max_batch_size == 5
    assert config.default_confidence_threshold == 0.65
    assert config.deterministic_confidence == 0.85
    assert config.grounding_required is False


def test_rejects_threshold_order_violation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTRACTOR_REVIEW_CONFIDENCE_THRESHOLD", "0.9")
    monkeypatch.setenv("EXTRACTOR_DEFAULT_CONFIDENCE_THRESHOLD", "0.5")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_rejects_confidence_threshold_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTRACTOR_DEFAULT_CONFIDENCE_THRESHOLD", "1.5")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)

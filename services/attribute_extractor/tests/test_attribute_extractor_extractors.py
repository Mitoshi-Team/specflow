"""Тесты базового класса экстракторов, реестра и скелетов."""

from __future__ import annotations

import pytest

from attribute_extractor.constants import (
    NER_EXTRACTOR_NAME,
    NER_EXTRACTOR_PRIORITY,
    RULE_EXTRACTOR_NAME,
    RULE_EXTRACTOR_PRIORITY,
)
from attribute_extractor.extractors import (
    BaseExtractor,
    ExtractorRegistry,
    NERExtractor,
    RuleExtractor,
    build_default_registry,
)
from specflow_contracts import CategorySchema, ProductCard


class _StubExtractor(BaseExtractor):
    """Тестовый экстрактор для проверки реестра."""

    def __init__(self, name: str, priority: int, supports_all: bool = True) -> None:
        self.name = name
        self.priority = priority
        self._supports_all = supports_all

    def extract(self, card: ProductCard, schema: CategorySchema) -> list:
        return []

    def supports(self, attribute_code: str, category: str | None) -> bool:
        return self._supports_all


def _make_card() -> ProductCard:
    return ProductCard(title="Ламинат 32 класс 1.5 м²", category="flooring")


def _make_schema() -> CategorySchema:
    return CategorySchema(category="flooring", schema_version="1.0.0")


def test_base_extractor_is_abstract() -> None:
    """Нельзя инстанцировать абстрактный BaseExtractor."""
    with pytest.raises(TypeError):
        BaseExtractor()  # type: ignore[abstract]


def test_skeleton_ner_extractor_returns_empty() -> None:
    """Скелетный NER-экстрактор возвращает пустой список кандидатов.

    RuleExtractor более не скелет — его поведение покрыто test_attribute_extractor_rule.py.
    """
    candidates = NERExtractor().extract(_make_card(), _make_schema())
    assert candidates == []


def test_skeleton_extractors_supports_default_true() -> None:
    """По умолчанию экстрактор поддерживает любой атрибут."""
    extractor = RuleExtractor()
    assert extractor.supports("color", category="flooring") is True
    assert extractor.supports("unknown", category=None) is True


def test_default_registry_order_and_names() -> None:
    """Реестр по умолчанию содержит все экстракторы в порядке cheap-first."""
    registry = build_default_registry()
    names = [e.name for e in registry]
    assert names == [
        RULE_EXTRACTOR_NAME,
        NER_EXTRACTOR_NAME,
    ]
    priorities = [e.priority for e in registry]
    assert priorities == [
        RULE_EXTRACTOR_PRIORITY,
        NER_EXTRACTOR_PRIORITY,
    ]


def test_registry_sorts_by_priority_ascending() -> None:
    """Регистрация вне порядка приводит к сортировке по возрастанию priority."""
    registry = ExtractorRegistry(
        [
            _StubExtractor("high", priority=50),
            _StubExtractor("low", priority=0),
            _StubExtractor("mid", priority=10),
        ]
    )
    assert [e.name for e in registry] == ["low", "mid", "high"]


def test_registry_stable_for_equal_priority() -> None:
    """При одинаковом priority порядок регистрации сохраняется."""
    first = _StubExtractor("a", priority=5)
    second = _StubExtractor("b", priority=5)
    registry = ExtractorRegistry([first, second])
    assert [e.name for e in registry] == ["a", "b"]

    registry = ExtractorRegistry([second, first])
    assert [e.name for e in registry] == ["b", "a"]


def test_registry_register_adds_and_sorts() -> None:
    """Метод register добавляет экстрактор и пересортирует реестр."""
    registry = ExtractorRegistry([_StubExtractor("x", priority=10)])
    registry.register(_StubExtractor("zero", priority=0))
    assert [e.name for e in registry] == ["zero", "x"]


def test_registry_get_by_name() -> None:
    """Получение экстрактора по имени работает корректно."""
    registry = ExtractorRegistry([_StubExtractor("rule", priority=0)])
    assert registry.get("rule") is not None
    assert registry.get("missing") is None


def test_registry_extractors_for_filters_by_supports() -> None:
    """extractors_for фильтрует по поддержке атрибута/категории."""
    registry = ExtractorRegistry(
        [
            _StubExtractor("ok1", priority=0, supports_all=True),
            _StubExtractor("nope", priority=1, supports_all=False),
            _StubExtractor("ok2", priority=2, supports_all=True),
        ]
    )
    filtered = registry.extractors_for("color", category="flooring")
    assert [e.name for e in filtered] == ["ok1", "ok2"]


def test_registry_len_and_iter_and_extractors_property() -> None:
    """Реестр поддерживает len, итерацию и свойство extractors (tuple)."""
    e1 = _StubExtractor("e1", priority=0)
    e2 = _StubExtractor("e2", priority=5)
    registry = ExtractorRegistry([e1, e2])
    assert len(registry) == 2
    assert list(registry) == [e1, e2]
    assert isinstance(registry.extractors, tuple)
    assert registry.extractors == (e1, e2)


def test_default_registry_missing_model_degrades(tmp_path) -> None:
    """Отсутствие каталога весов — NER недоступен, пайплайн деградирует до правил."""
    registry = build_default_registry(ner_model_path=tmp_path / "нет-модели")
    ner = registry.get(NER_EXTRACTOR_NAME)
    assert ner is not None
    assert ner.is_available() is False
    assert ner.predictor is None


def test_default_registry_auto_loads_model(monkeypatch, tmp_path) -> None:
    """Существующий каталог весов: предиктор создаётся автоматически с порогом."""
    created = {}

    class _FakePredictor:
        def __init__(self, model_path, min_score=0.0):
            created["model_path"] = model_path
            created["min_score"] = min_score
            created["calls"] = 0

        def predict(self, text):
            created["calls"] += 1
            return []

    import attribute_extractor.ner_model as ner_model_module

    monkeypatch.setattr(ner_model_module, "TransformersSpanPredictor", _FakePredictor)
    (tmp_path / "ner").mkdir()
    registry = build_default_registry(ner_model_path=tmp_path / "ner", ner_span_min_score=0.7)
    ner = registry.get(NER_EXTRACTOR_NAME)
    assert str(created["model_path"]) == str(tmp_path / "ner")
    assert created["min_score"] == 0.7
    # Автоматическая загрузка обязана быть доступной (с резолвером Этапа 5).
    assert ner.is_available() is True
    assert created["calls"] == 0


class _PredictorStub:
    """Предиктор без резолвера: сам по себе кандидатов не формирует."""

    def predict(self, text: str) -> list:
        return []


def test_default_registry_injected_predictor_without_resolver_stays_unavailable() -> None:
    """Инъекция предиктора строит резолвер автоматически и делает NER доступным.

    Отличается от прежнего каркаса: Этап 5 (резолв) инициализируется вместе с
    моделью, без отдельного провода.
    """
    registry = build_default_registry(
        ner_model_path=None,
        ner_predictor=_PredictorStub(),
    )
    ner = registry.get(NER_EXTRACTOR_NAME)
    assert ner is not None
    assert ner.is_available() is True

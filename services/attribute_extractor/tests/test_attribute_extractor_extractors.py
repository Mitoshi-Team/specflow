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


@pytest.mark.parametrize(
    "extractor_cls",
    [
        RuleExtractor,
        NERExtractor,
    ],
)
def test_skeleton_extractors_return_empty(extractor_cls) -> None:
    """Скелетные экстракторы возвращают пустой список кандидатов."""
    extractor = extractor_cls()
    candidates = extractor.extract(_make_card(), _make_schema())
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

"""Базовая абстракция экстрактора атрибутов."""

from abc import ABC, abstractmethod

from specflow_contracts import AttributeCandidate, CategorySchema, ProductCard


class BaseExtractor(ABC):
    """Общий интерфейс экстрактора кандидатов атрибутов.

    Экстракторы запускаются каскадом (cheap-first) в порядке возрастания
    ``priority``. Каждый экстрактор обязан возвращать кандидатов с заполненными
    ``extraction_method``, ``confidence``, ``is_confirmed_in_text`` и
    ``source_spans``/``evidence_text`` (см. attribute_extractor.md).
    """

    name: str
    """Уникальное имя экстрактора (совпадает со значением ``ExtractionMethod``)."""

    priority: int
    """Приоритет запуска: меньшее значение — раньше в каскаде."""

    @abstractmethod
    def extract(self, card: ProductCard, schema: CategorySchema) -> list[AttributeCandidate]:
        """Извлечь кандидатов атрибутов для карточки в рамках схемы категории."""
        raise NotImplementedError

    def supports(self, attribute_code: str, category: str | None) -> bool:
        """Поддерживает ли экстрактор данный атрибут/категорию.

        По умолчанию экстрактор считает, что поддерживает любой атрибут.
        Экстракторы с ограниченной областью применения переопределяют метод.
        """
        return True

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r}, priority={self.priority})"

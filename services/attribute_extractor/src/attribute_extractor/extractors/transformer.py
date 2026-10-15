"""Transformer-экстрактор (скелет)."""

from attribute_extractor.constants import (
    TRANSFORMER_EXTRACTOR_NAME,
    TRANSFORMER_EXTRACTOR_PRIORITY,
)
from attribute_extractor.extractors.base import BaseExtractor
from specflow_contracts import AttributeCandidate, CategorySchema, ProductCard


class TransformerExtractor(BaseExtractor):
    """Извлечение атрибутов предобученной transformer-моделью.

    Заглушка каскада: подключение ML-трансформера появится на следующем
    этапе; пока возвращает пустой список кандидатов.
    """

    name = TRANSFORMER_EXTRACTOR_NAME
    priority = TRANSFORMER_EXTRACTOR_PRIORITY

    def extract(self, card: ProductCard, schema: CategorySchema) -> list[AttributeCandidate]:
        return []

"""LLM-экстрактор (скелет)."""

from attribute_extractor.constants import LLM_EXTRACTOR_NAME, LLM_EXTRACTOR_PRIORITY
from attribute_extractor.extractors.base import BaseExtractor
from specflow_contracts import AttributeCandidate, CategorySchema, ProductCard


class LLMExtractor(BaseExtractor):
    """Извлечение атрибутов внешней LLM (с нормализацией и grounding).

    Заглушка каскада: адаптер к LLM-провайдеру появится на следующем этапе;
    пока возвращает пустой список кандидатов.
    """

    name = LLM_EXTRACTOR_NAME
    priority = LLM_EXTRACTOR_PRIORITY

    def extract(self, card: ProductCard, schema: CategorySchema) -> list[AttributeCandidate]:
        return []

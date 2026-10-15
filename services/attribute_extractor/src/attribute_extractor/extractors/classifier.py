"""Экстрактор-классификатор (скелет)."""

from attribute_extractor.constants import (
    CLASSIFIER_EXTRACTOR_NAME,
    CLASSIFIER_EXTRACTOR_PRIORITY,
)
from attribute_extractor.extractors.base import BaseExtractor
from specflow_contracts import AttributeCandidate, CategorySchema, ProductCard


class ClassifierExtractor(BaseExtractor):
    """Классификация кандидатов по атрибутам на основе обучаемой модели.

    Заглушка каскада: подключение классификатора появится на следующем
    этапе; пока возвращает пустой список кандидатов.
    """

    name = CLASSIFIER_EXTRACTOR_NAME
    priority = CLASSIFIER_EXTRACTOR_PRIORITY

    def extract(self, card: ProductCard, schema: CategorySchema) -> list[AttributeCandidate]:
        return []

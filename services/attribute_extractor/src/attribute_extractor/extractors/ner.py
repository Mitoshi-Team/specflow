"""NER-экстрактор (скелет)."""

from attribute_extractor.constants import NER_EXTRACTOR_NAME, NER_EXTRACTOR_PRIORITY
from attribute_extractor.extractors.base import BaseExtractor
from specflow_contracts import AttributeCandidate, CategorySchema, ProductCard


class NERExtractor(BaseExtractor):
    """Извлечение именованных сущностей (материалы, бренды, числа).

    Заглушка каскада: подключение NER-модели появится на следующем этапе;
    пока возвращает пустой список кандидатов.
    """

    name = NER_EXTRACTOR_NAME
    priority = NER_EXTRACTOR_PRIORITY

    def extract(self, card: ProductCard, schema: CategorySchema) -> list[AttributeCandidate]:
        return []

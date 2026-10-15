"""Словарный экстрактор (скелет)."""

from attribute_extractor.constants import DICT_EXTRACTOR_NAME, DICT_EXTRACTOR_PRIORITY
from attribute_extractor.extractors.base import BaseExtractor
from specflow_contracts import AttributeCandidate, CategorySchema, ProductCard


class DictExtractor(BaseExtractor):
    """Поиск по синонимам/справочникам: enum-значения, бренды и т.п.

    Заглушка каскада: реализация словарей появится на следующем этапе;
    пока возвращает пустой список кандидатов.
    """

    name = DICT_EXTRACTOR_NAME
    priority = DICT_EXTRACTOR_PRIORITY

    def extract(self, card: ProductCard, schema: CategorySchema) -> list[AttributeCandidate]:
        return []

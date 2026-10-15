"""Экстрактор на основе правил и шаблонов (скелет)."""

from attribute_extractor.constants import RULE_EXTRACTOR_NAME, RULE_EXTRACTOR_PRIORITY
from attribute_extractor.extractors.base import BaseExtractor
from specflow_contracts import AttributeCandidate, CategorySchema, ProductCard


class RuleExtractor(BaseExtractor):
    """Регулярные выражения, шаблоны ключевых фраз и парсинг единиц.

    Заглушка каскада: реализация детерминированных правил появится на
    следующем этапе; пока возвращает пустой список кандидатов.
    """

    name = RULE_EXTRACTOR_NAME
    priority = RULE_EXTRACTOR_PRIORITY

    def extract(self, card: ProductCard, schema: CategorySchema) -> list[AttributeCandidate]:
        return []

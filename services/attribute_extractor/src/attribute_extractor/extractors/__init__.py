"""Экстракторы атрибутов и их реестр."""

from attribute_extractor.constants import DEFAULT_BRAND_VOCAB_PATH
from attribute_extractor.extractors.base import BaseExtractor
from attribute_extractor.extractors.ner import NERExtractor
from attribute_extractor.extractors.registry import ExtractorRegistry
from attribute_extractor.extractors.rule import RuleExtractor
from attribute_extractor.references import load_brand_vocab

__all__ = [
    "BaseExtractor",
    "ExtractorRegistry",
    "NERExtractor",
    "RuleExtractor",
    "build_default_registry",
]


def build_default_registry(*, brand_vocab_path: str | None = None) -> ExtractorRegistry:
    """Собрать реестр со стандартным порядком каскада (cheap-first).

    Бренд-словарь загружается из версонируемого ассета
    (``DEFAULT_BRAND_VOCAB_PATH`` или переопределение через
    ``brand_vocab_path``); отсутствие ассета — штатный вариант без брендовых
    правил.
    """
    path = brand_vocab_path or DEFAULT_BRAND_VOCAB_PATH
    return ExtractorRegistry(
        [
            RuleExtractor(brand_vocab=load_brand_vocab(path)),
            NERExtractor(),
        ]
    )

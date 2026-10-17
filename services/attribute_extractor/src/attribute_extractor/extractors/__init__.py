"""Экстракторы атрибутов и их реестр."""

from attribute_extractor.extractors.base import BaseExtractor
from attribute_extractor.extractors.ner import NERExtractor
from attribute_extractor.extractors.registry import ExtractorRegistry
from attribute_extractor.extractors.rule import RuleExtractor

__all__ = [
    "BaseExtractor",
    "ExtractorRegistry",
    "NERExtractor",
    "RuleExtractor",
    "build_default_registry",
]


def build_default_registry() -> ExtractorRegistry:
    """Собрать реестр со стандартным порядком каскада (cheap-first)."""
    return ExtractorRegistry(
        [
            RuleExtractor(),
            NERExtractor(),
        ]
    )

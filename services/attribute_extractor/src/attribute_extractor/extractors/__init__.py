"""Экстракторы атрибутов и их реестр."""

from attribute_extractor.extractors.base import BaseExtractor
from attribute_extractor.extractors.classifier import ClassifierExtractor
from attribute_extractor.extractors.dictionary import DictExtractor
from attribute_extractor.extractors.llm import LLMExtractor
from attribute_extractor.extractors.ner import NERExtractor
from attribute_extractor.extractors.registry import ExtractorRegistry
from attribute_extractor.extractors.rule import RuleExtractor
from attribute_extractor.extractors.transformer import TransformerExtractor

__all__ = [
    "BaseExtractor",
    "ClassifierExtractor",
    "DictExtractor",
    "ExtractorRegistry",
    "LLMExtractor",
    "NERExtractor",
    "RuleExtractor",
    "TransformerExtractor",
    "build_default_registry",
]


def build_default_registry() -> ExtractorRegistry:
    """Собрать реестр со стандартным порядком каскада (cheap-first)."""
    return ExtractorRegistry(
        [
            RuleExtractor(),
            DictExtractor(),
            NERExtractor(),
            ClassifierExtractor(),
            TransformerExtractor(),
            LLMExtractor(),
        ]
    )

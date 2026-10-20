"""Экстракторы атрибутов и их реестр."""

from __future__ import annotations

from attribute_extractor.constants import DEFAULT_BRAND_VOCAB_PATH
from attribute_extractor.extractors.base import BaseExtractor
from attribute_extractor.extractors.ner import NERExtractor, SpanPredictor
from attribute_extractor.extractors.registry import ExtractorRegistry
from attribute_extractor.extractors.rule import RuleExtractor
from attribute_extractor.fields import FieldResolver
from attribute_extractor.references import load_brand_vocab

__all__ = [
    "BaseExtractor",
    "ExtractorRegistry",
    "NERExtractor",
    "SpanPredictor",
    "RuleExtractor",
    "build_default_registry",
]


def build_default_registry(
    *,
    brand_vocab_path: str | None = None,
    ner_predictor: SpanPredictor | None = None,
    ner_resolver: FieldResolver | None = None,
) -> ExtractorRegistry:
    """Собрать реестр со стандартным порядком каскада (cheap-first).

    Бренд-словарь загружается из версонируемого ассета
    (``DEFAULT_BRAND_VOCAB_PATH`` или переопределение через
    ``brand_vocab_path``); отсутствие ассета — штатный вариант без брендовых
    правил. NER подключается только с инъекцией ``ner_predictor`` (модель
    Фазы B) и ``ner_resolver`` (Этап 5); без них экстрактор недоступен и
    пайплайн штатно деградирует до правил.
    """
    path = brand_vocab_path or DEFAULT_BRAND_VOCAB_PATH
    ner = NERExtractor(predictor=ner_predictor, resolver=ner_resolver)
    if ner_predictor is not None:
        ner.load()
    return ExtractorRegistry(
        [
            RuleExtractor(brand_vocab=load_brand_vocab(path)),
            ner,
        ]
    )

"""Экстракторы атрибутов и их реестр."""

from __future__ import annotations

import logging

from attribute_extractor.constants import (
    DEFAULT_BRAND_VOCAB_PATH,
    DEFAULT_MATCH_THRESHOLD,
    DEFAULT_NER_MODEL_PATH,
    DEFAULT_NER_SPAN_MIN_SCORE,
)
from attribute_extractor.extractors.base import BaseExtractor
from attribute_extractor.extractors.ner import NERExtractor, SpanPredictor
from attribute_extractor.extractors.registry import ExtractorRegistry
from attribute_extractor.extractors.rule import RuleExtractor
from attribute_extractor.fields import FieldResolver
from attribute_extractor.paths import resolve_artifact_path
from attribute_extractor.references import load_brand_vocab

logger = logging.getLogger(__name__)

__all__ = [
    "BaseExtractor",
    "ExtractorRegistry",
    "NERExtractor",
    "SpanPredictor",
    "RuleExtractor",
    "build_default_registry",
]


def _load_ner_predictor(
    model_path: str | None,
    *,
    min_score: float,
) -> SpanPredictor | None:
    """Загрузить модель NER, если каталог весов существует; иначе None.

    Ошибки загрузки (нет torch/transformers, битый каталог) не прерывают
    сборку реестра: пайплайн штатно деградирует до правил, причина с traceback
    в логе — молчаливый отказ маскировал бы выключенную модель.
    """
    if not model_path:
        return None
    resolved = resolve_artifact_path(model_path)
    if not resolved.is_dir():
        return None
    try:
        from attribute_extractor.ner_model import TransformersSpanPredictor

        return TransformersSpanPredictor(str(resolved), min_score=min_score)
    except Exception:  # noqa: BLE001 — деградация по дизайну (модель не обязательна)
        logger.warning(
            "NER-модель из %s не загружена — пайплайн работает на правилах",
            model_path,
            exc_info=True,
        )
        return None


def build_default_registry(
    *,
    brand_vocab_path: str | None = None,
    ner_predictor: SpanPredictor | None = None,
    ner_resolver: FieldResolver | None = None,
    ner_model_path: str | None = None,
    ner_span_min_score: float = DEFAULT_NER_SPAN_MIN_SCORE,
    match_threshold: float = DEFAULT_MATCH_THRESHOLD,
) -> ExtractorRegistry:
    """Собрать реестр со стандартным порядком каскада (cheap-first).

    Бренд-словарь загружается из версонируемого ассета
    (``DEFAULT_BRAND_VOCAB_PATH`` или переопределение через
    ``brand_vocab_path``); отсутствие ассета — штатный вариант без брендовых
    правил. NER подключается по инъекции ``ner_predictor``/``ner_resolver``;
    если предиктора нет, пытается загрузиться модель из ``ner_model_path``
    (отсутствие каталога весов — штатная деградация до правил). Пороги
    ``ner_span_min_score`` (отсечение слабых спанов) и ``match_threshold``
    (векторный матч полей) калибруются на gold-наборе.
    """
    path = brand_vocab_path or DEFAULT_BRAND_VOCAB_PATH
    if ner_predictor is None:
        ner_predictor = _load_ner_predictor(ner_model_path, min_score=ner_span_min_score)
    if ner_predictor is not None and ner_resolver is None:
        ner_resolver = FieldResolver(match_threshold=match_threshold)
    ner = NERExtractor(predictor=ner_predictor, resolver=ner_resolver)
    if ner_predictor is not None:
        ner.load()
    return ExtractorRegistry(
        [
            RuleExtractor(brand_vocab=load_brand_vocab(path)),
            ner,
        ]
    )

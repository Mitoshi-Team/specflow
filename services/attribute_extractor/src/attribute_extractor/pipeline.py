"""Оркестратор каскада Этапов 0–11 (architecture.md, §5 сценарий 1).

Цепочка: clean + schema (0-1) → rules (3) / NER (4) → нормализация (6) →
merge (8) → grounding (9) → уверенность и статус (10) → результат (11).
Этапы включаются тумблерами ``Settings.enable_*`` (env ``EXTRACTOR_ENABLE_*``);
NER-модель без весов и векторный индекс не прерывают пайплайн — действует
graceful degradation (сценарий 3): пайплайн работает на правилах.

Резолв полей (Этап 5) выполняется внутри NER-пути над парами
``CHARACTERISTIC``/``PROPERTY``; тумблер ``enable_vector_match`` применяется
при его инициализации (Фаза B). Rule-кандидаты идут с кодом поля напрямую.

Rules-fallback (Этап 7) после NER заполняет только те **обязательные** поля
схемы, которые NER-путь не закрыл; полными правилами NER не дублируется.
"""

from __future__ import annotations

import time

from attribute_extractor.confidence import ConfidenceCalculator
from attribute_extractor.config import Settings
from attribute_extractor.constants import (
    CONFLICT_FEATURE_KEY,
    NER_EXTRACTOR_NAME,
    RULE_EXTRACTOR_NAME,
)
from attribute_extractor.extractors import build_default_registry
from attribute_extractor.extractors.registry import ExtractorRegistry
from attribute_extractor.grounding import GroundingValidator
from attribute_extractor.merging import CandidateMerger
from attribute_extractor.normalization import ValueNormalizer
from attribute_extractor.preprocessing import CardPreprocessor, PreprocessedCard
from specflow_contracts import (
    AttributeCandidate,
    CategorySchema,
    ExtractionResult,
    ExtractionStatus,
    ProductCard,
)


class ExtractPipeline:
    """Пайплайн одиночного извлечения по карточке (Этапы 0–11)."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        registry: ExtractorRegistry | None = None,
        preprocessor: CardPreprocessor | None = None,
        normalizer: ValueNormalizer | None = None,
        merger: CandidateMerger | None = None,
        grounding: GroundingValidator | None = None,
        confidence: ConfidenceCalculator | None = None,
    ) -> None:
        self._settings = settings if settings is not None else Settings()
        self._registry = registry if registry is not None else build_default_registry()
        self._rule = self._registry.get(RULE_EXTRACTOR_NAME)
        self._ner = self._registry.get(NER_EXTRACTOR_NAME)
        self._preprocessor = preprocessor if preprocessor is not None else CardPreprocessor()
        self._normalizer = normalizer
        if self._normalizer is None and self._settings.normalization_enabled:
            self._normalizer = ValueNormalizer(
                unit_conversion_enabled=self._settings.unit_conversion_enabled,
                enum_strict=self._settings.enum_strict,
            )
        self._merger = merger if merger is not None else CandidateMerger()
        self._grounding = grounding if grounding is not None else GroundingValidator()
        self._confidence = (
            confidence
            if confidence is not None
            else ConfidenceCalculator(self._settings.deterministic_confidence)
        )

    def extract(
        self, card: ProductCard, *, confidence_threshold: float | None = None
    ) -> ExtractionResult:
        """Извлечь атрибуты карточки и вернуть ``ExtractionResult`` (Этап 11).

        ``confidence_threshold`` — локальное переопределение порога
        «автоматическое принятие» для одного вызова (batch-эндпоинт передаёт
        ``threshold_override``); ``Settings`` при этом не мутирует.
        """
        started = time.monotonic()
        if not _has_text(card):
            # Нет текста — подтвердить значения нельзя, карточка уходит на
            # ручную проверку (attribute_extractor.md, §6: пустой список,
            # needs_review=true, статус skipped).
            return self._finish(
                card,
                attributes=[],
                status=ExtractionStatus.SKIPPED,
                needs_review=True,
                low_confidence_count=0,
                started=started,
            )
        # Нарушение инварианта очистки (TextCleanupInvariantError) пробрасывается
        # наружу — API транслирует его в 500 с кодом invariant_violation
        # (api_contract.md, 4.1).
        preprocessed = self._preprocessor.preprocess(card)
        candidates = self._collect_candidates(preprocessed)
        # Этап 10 (расчёт уверенности) выполняется сразу после извлечения, до
        # нормализации: уверенность задаётся методом (structured/rule/ner), а
        # нормализация может лишь понизить её (enum вне словаря, Этап 6).
        candidates = self._confidence.apply(candidates)

        if self._normalizer is not None:
            candidates = self._normalizer.normalize_all(candidates, preprocessed.category_schema)
        candidates = self._merger.merge(candidates)
        if self._settings.grounding_required:
            candidates = self._grounding.filter(candidates, card)

        auto = (
            self._settings.default_confidence_threshold
            if confidence_threshold is None
            else confidence_threshold
        )
        low_confidence_count = sum(1 for candidate in candidates if candidate.confidence < auto)
        has_conflict = any(
            candidate.features and CONFLICT_FEATURE_KEY in candidate.features
            for candidate in candidates
        )
        required_missing = _required_missing(candidates, preprocessed)
        needs_review = bool(low_confidence_count or has_conflict or required_missing)
        if needs_review:
            status = (
                ExtractionStatus.PARTIAL if required_missing else ExtractionStatus.LOW_CONFIDENCE
            )
        else:
            status = ExtractionStatus.OK
        attributes = sorted(candidates, key=lambda candidate: candidate.attribute_code)
        return self._finish(
            card,
            attributes=attributes,
            status=status,
            needs_review=needs_review,
            low_confidence_count=low_confidence_count,
            started=started,
        )

    def _collect_candidates(self, preprocessed: PreprocessedCard) -> list[AttributeCandidate]:
        """Этапы 3-4-7: NER-путь, полный rule-путь либо fallback правил.

        - NER недоступен/выключен (сценарий 3) → полный rule-путь.
        - NER дал кандидатов → правила дополняют только незакрытые
          обязательные поля (Этап 7) при ``enable_rules_fallback``.
        """
        card = preprocessed.card
        schema = preprocessed.category_schema
        rule = self._rule
        ner_candidates = self._run_ner(card, schema)
        if not ner_candidates:
            if rule is None or not self._settings.enable_rules:
                return []
            return list(rule.extract(card, schema))
        if (
            rule is None
            or not self._settings.enable_rules
            or not self._settings.enable_rules_fallback
        ):
            return ner_candidates
        closed_required = {candidate.attribute_code for candidate in ner_candidates}
        fallback_codes = {
            attribute.code
            for attribute in schema.required_attributes
            if attribute.code not in closed_required
        }
        if not fallback_codes:
            return ner_candidates
        return ner_candidates + rule.extract_for_missing(card, schema, fallback_codes)

    def _run_ner(self, card: ProductCard, schema: CategorySchema) -> list[AttributeCandidate]:
        """Этап 4: NER-кандидаты; без модели/при ошибке — пусто (degradation)."""
        ner = self._ner
        if not self._settings.enable_ner or ner is None or not _extractor_available(ner):
            return []
        try:
            return list(ner.extract(card, schema))
        except Exception:
            return []

    def _finish(
        self,
        card: ProductCard,
        *,
        attributes: list[AttributeCandidate],
        status: ExtractionStatus,
        needs_review: bool,
        low_confidence_count: int,
        started: float,
    ) -> ExtractionResult:
        return ExtractionResult(
            attributes=attributes,
            status=status,
            needs_review=needs_review,
            pipeline_version=self._settings.pipeline_version,
            product_id=card.product_id,
            category_id=card.category_id,
            category_name=card.category_name,
            low_confidence_count=low_confidence_count,
            processing_time_ms=int((time.monotonic() - started) * 1000),
        )


def _has_text(card: ProductCard) -> bool:
    """Есть ли текстовый вход пайплайна (title/description, seller-атрибуты — нет)."""
    if card.title and card.title.strip():
        return True
    return bool(card.description and card.description.strip())


def _extractor_available(extractor: object) -> bool:
    """Доступность экстрактора: NER требует загруженной модели, rule — всегда да."""
    available = getattr(extractor, "is_available", None)
    return available is None or bool(available())


def _required_missing(
    candidates: list[AttributeCandidate], preprocessed: PreprocessedCard
) -> list[str]:
    """Коды обязательных атрибутов схемы, не закрытые кандидатами."""
    present = {candidate.attribute_code for candidate in candidates}
    return [
        attribute.code
        for attribute in preprocessed.category_schema.required_attributes
        if attribute.code not in present
    ]

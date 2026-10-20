"""Тесты NER-экстрактора: пейринг и резолв полей (Этапы 4-5).

Модель не нужна: предсказания спанов подаются фейковым ``SpanPredictor``,
резолв — поверх временного каталога полей. Внешние сервисы не используются.
"""

from __future__ import annotations

import pytest

from attribute_extractor.catalog_store import CatalogStore
from attribute_extractor.constants import DEFAULT_MATCH_THRESHOLD
from attribute_extractor.extractors import ner
from attribute_extractor.fields import FieldResolver
from specflow_contracts import ExtractionMethod, ProductCard, SpanField


class _StaticPredictor:
    """FAKE predictor: фиксированные спаны независимо от текста."""

    def __init__(self, spans: list[ner.NERSpan]) -> None:
        self._spans = spans

    def predict(self, text: str) -> list[ner.NERSpan]:
        return self._spans


def _resolver(tmp_path, blocklist: list[str] | None = None) -> FieldResolver:
    store = CatalogStore(tmp_path / "cat.json", tmp_path / "bl.txt")
    store.save_catalog({"version": "1.0.0", "entries": [{"code": "color", "name_ru": "Цвет"}]})
    if blocklist:
        store.save_blocklist(blocklist)
    return FieldResolver(store=store)


def _card(title: str = "Смартфон Acme цвет черный") -> ProductCard:
    return ProductCard(product_id="p1", title=title, category_name="Смартфоны")


def test_ner_span_pairing():
    spans = [
        ner.NERSpan(text="Цвет", label="CHARACTERISTIC", start=0, end=4, score=0.9),
        ner.NERSpan(text="черный", label="PROPERTY", start=5, end=11, score=0.9),
    ]
    pairs = ner.NERExtractor().extract_pairs(spans)
    assert pairs
    assert pairs[0].characteristic == "Цвет"
    assert pairs[0].property == "черный"
    assert pairs[0].ner_score > 0.0


def test_extract_resolves_canonical_match_and_anchors_spans(tmp_path) -> None:
    extractor = ner.NERExtractor(
        predictor=_StaticPredictor(
            [
                ner.NERSpan(text="Цвет", label="CHARACTERISTIC", start=10, end=14, score=0.9),
                ner.NERSpan(text="черный", label="PROPERTY", start=10, end=16, score=0.9),
            ]
        ),
        resolver=_resolver(tmp_path),
    )
    extractor.load()
    candidates = extractor.extract(_card())

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.attribute_code == "color"
    assert candidate.is_new_field is False
    assert candidate.match_score is not None
    assert candidate.match_score >= DEFAULT_MATCH_THRESHOLD
    assert candidate.ner_score == pytest.approx(0.9)
    assert candidate.extraction_method == ExtractionMethod.NER
    assert candidate.is_confirmed_in_text is True
    assert candidate.evidence_text == "черный"
    assert candidate.features == {"characteristic": "Цвет"}
    value_span = candidate.source_spans[0]
    assert value_span.field == SpanField.TITLE
    assert _card().title[value_span.start : value_span.end] == "черный"


def test_extract_below_threshold_becomes_new_field(tmp_path) -> None:
    resolver = _resolver(tmp_path)
    extractor = ner.NERExtractor(
        predictor=_StaticPredictor(
            [
                ner.NERSpan(text="Матрица", label="CHARACTERISTIC", start=0, end=7, score=0.9),
                ner.NERSpan(text="IPS", label="PROPERTY", start=0, end=3, score=0.9),
            ]
        ),
        resolver=resolver,
    )
    extractor.load()
    card = ProductCard(product_id="p2", title="Телефон Acme Pro IPS", category_name="Смартфоны")
    candidates = extractor.extract(card)

    assert len(candidates) == 1
    candidate = candidates[0]
    # Имя вне каталога: slug авто-нового поля, канон назначает только аудит.
    assert candidate.attribute_code == "matritsa"
    assert candidate.is_new_field is True
    assert candidate.match_score is not None
    assert candidate.match_score < DEFAULT_MATCH_THRESHOLD
    assert resolver.catalog.has("matritsa")


def test_extract_drops_blocked_characteristic(tmp_path) -> None:
    extractor = ner.NERExtractor(
        predictor=_StaticPredictor(
            [
                ner.NERSpan(text="Продавец", label="CHARACTERISTIC", start=0, end=8, score=0.9),
                ner.NERSpan(text="Acme", label="PROPERTY", start=0, end=4, score=0.9),
            ]
        ),
        resolver=_resolver(tmp_path, ["продавец"]),
    )
    extractor.load()
    assert extractor.extract(_card()) == []


def test_extract_confirmed_only_when_value_in_text(tmp_path) -> None:
    extractor = ner.NERExtractor(
        predictor=_StaticPredictor(
            [
                ner.NERSpan(text="Цвет", label="CHARACTERISTIC", start=0, end=4, score=0.9),
                ner.NERSpan(text="фиолетовый", label="PROPERTY", start=0, end=10, score=0.9),
            ]
        ),
        resolver=_resolver(tmp_path),
    )
    extractor.load()
    candidate = extractor.extract(_card())[0]

    assert candidate.is_confirmed_in_text is False
    # Имя найдено в тексте, значение — нет: остаётся спан имени без кода
    # значения; grounding-фильтр пайплайна такие кандидаты отбрасывает.
    assert len(candidate.source_spans) == 1


def test_no_predictor_is_unavailable() -> None:
    extractor = ner.NERExtractor(model_path=None)
    extractor.load()
    assert extractor.is_available() is False
    assert extractor.extract(_card()) == []

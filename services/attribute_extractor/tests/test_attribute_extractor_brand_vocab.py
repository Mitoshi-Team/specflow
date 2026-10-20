"""Тесты бренд-словаря: ассет, загрузка и брендовые правила RuleExtractor."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from attribute_extractor.extractors.rule import RuleExtractor
from attribute_extractor.preprocessing import generic_schema
from attribute_extractor.references import load_brand_vocab
from specflow_contracts import ProductCard


def _card(title: str) -> ProductCard:
    return ProductCard(sku_id="t1", title=title, description="")


def test_load_brand_vocab_reads_default_asset() -> None:
    vocab = load_brand_vocab()
    assert vocab is not None
    assert len(vocab.names) > 150
    assert vocab.version
    lowered = {name.casefold() for name in vocab.names}
    assert {"apple", "samsung", "xiaomi"} <= lowered


def test_load_brand_vocab_missing_file_returns_none(tmp_path: Path) -> None:
    assert load_brand_vocab(tmp_path / "absent.json") is None


def test_load_brand_vocab_corrupt_json_returns_none_and_logs(tmp_path: Path, caplog) -> None:
    """Битый JSON деградирует до ``None`` (без брендовых правил), но с ERROR-логом."""
    import logging

    path = tmp_path / "vocab.json"
    path.write_text("{не json", encoding="utf-8")
    with caplog.at_level(logging.ERROR, logger="attribute_extractor.references"):
        assert load_brand_vocab(path) is None
    assert any(str(path) in record.getMessage() for record in caplog.records)


def test_load_brand_vocab_invalid_schema_returns_none_and_logs(tmp_path: Path, caplog) -> None:
    """Валидный JSON, не проходящий схему BrandVocab, — та же деградация с логом."""
    import json as json_module
    import logging

    path = tmp_path / "vocab.json"
    path.write_text(json_module.dumps({"names": "не список"}), encoding="utf-8")
    with caplog.at_level(logging.ERROR, logger="attribute_extractor.references"):
        assert load_brand_vocab(path) is None
    assert any(str(path) in record.getMessage() for record in caplog.records)


def test_build_default_registry_survives_corrupt_brand_vocab(tmp_path: Path, monkeypatch) -> None:
    """Порча ассета не роняет сборку реестра (и старт сервиса) — деградация."""
    from attribute_extractor import extractors

    path = tmp_path / "vocab.json"
    path.write_text("{не json", encoding="utf-8")
    monkeypatch.setattr(extractors, "DEFAULT_BRAND_VOCAB_PATH", str(path))

    registry = extractors.build_default_registry()
    extractor = registry.get("rule")
    assert isinstance(extractor, RuleExtractor)
    # Без словаря брендовые правила молчат: Apple из заголовка не извлекается.
    candidates = [
        c
        for c in extractor.extract(_card("Смартфон Apple iPhone 13 Pro"), generic_schema())
        if c.attribute_code == "brand"
    ]
    assert candidates == []


def test_build_default_registry_wires_brand_vocab() -> None:
    from attribute_extractor.extractors import build_default_registry

    registry = build_default_registry()
    extractor = registry.get("rule")
    assert isinstance(extractor, RuleExtractor)
    card = _card("Смартфон Apple iPhone 13 Pro 256 ГБ")
    candidates = [
        c for c in extractor.extract(card, generic_schema()) if c.attribute_code == "brand"
    ]
    assert [c.normalized_value for c in candidates] == ["Apple"]


def test_rule_extractor_applies_case_variants_and_aliases(tmp_path: Path) -> None:
    vocab_path = tmp_path / "vocab.json"
    vocab_path.write_text(
        json.dumps(
            {
                "names": ["Samsung"],
                "aliases": {"самсунг": "Samsung"},
                "stopwords": ["нет бренда"],
            }
        ),
        encoding="utf-8",
    )
    vocab = load_brand_vocab(vocab_path)
    extractor = RuleExtractor(brand_vocab=vocab)
    schema = generic_schema()

    upper = extractor.extract(_card("Ultrabook SAMSUNG UltraBook 15.6"), schema)
    assert any(c.attribute_code == "brand" and c.normalized_value == "Samsung" for c in upper)

    cyrillic = extractor.extract(_card("смартфон Самсунг Galaxy"), schema)
    assert any(c.attribute_code == "brand" and c.normalized_value == "Samsung" for c in cyrillic)


def test_rule_extractor_skips_unknown_words_without_vocab(tmp_path: Path) -> None:
    extractor = RuleExtractor(brand_vocab=None)
    card = _card("Ноутбук Acer Nitro 5")
    candidates = [
        c for c in extractor.extract(card, generic_schema()) if c.attribute_code == "brand"
    ]
    assert candidates == []


def test_rule_extractor_stopword_blocks_placeholder(tmp_path: Path) -> None:
    vocab_path = tmp_path / "vocab.json"
    vocab_path.write_text(
        json.dumps({"names": ["Top"], "stopwords": ["TOP"]}),
        encoding="utf-8",
    )
    vocab = load_brand_vocab(vocab_path)
    extractor = RuleExtractor(brand_vocab=vocab)
    candidates = extractor.extract(_card("Монитор TOP 27"), generic_schema())
    assert all(c.attribute_code != "brand" for c in candidates)


@pytest.mark.parametrize("brand", ["Apple", "SONY", "Huawei"])
def test_real_vocab_matches_case_variants(brand: str) -> None:
    vocab = load_brand_vocab()
    assert vocab is not None
    canonical = vocab.resolve(brand)
    assert canonical is not None

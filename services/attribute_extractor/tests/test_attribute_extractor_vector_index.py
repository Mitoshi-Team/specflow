"""Тесты VectorIndex: лексический fallback, семантический индекс и фабрика."""

from __future__ import annotations

import math

import pytest

from attribute_extractor import vector_index


class FakeEncoder:
    """Заглушка sentence-transformers модели: детерминированный словарь векторов."""

    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self._mapping = mapping

    def encode(self, text: str, normalize_embeddings: bool = True) -> list[float]:
        vec = self._mapping.get(text, [0.0, 0.0])
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def test_lexical_vector_index_fallback():
    vi = vector_index.LexicalVectorIndex()
    vi.add("color")
    vi.add("storage")
    q = vi.embed("цвет")
    res = vi.search(q, k=2)
    assert res[0][1] >= 0.0


def test_lexical_add_twice_no_dup():
    vi = vector_index.LexicalVectorIndex()
    vi.add("ram")
    vi.add("ram")
    assert len(vi._keys) == 1


def test_lexical_coverage_matches_token_in_rich_field():
    vi = vector_index.LexicalVectorIndex()
    vi.add("ram", vi.embed("Оперативная память ; ОЗУ ; RAM"))
    res = vi.search(vi.embed("озу"), k=1)
    assert res[0][0] == "ram"
    assert res[0][1] == pytest.approx(1.0)


def test_encoder_index_uses_injected_model():
    fake = FakeEncoder({"ozu": [1.0, 0.0], "ram": [1.0, 0.0], "cpu": [0.0, 1.0]})
    idx = vector_index.EncoderVectorIndex(model=fake)
    idx.add("ram", idx.embed("ram"))
    idx.add("processor", idx.embed("cpu"))
    res = idx.search(idx.embed("ozu"), k=2)
    assert res[0][0] == "ram"
    assert res[0][1] >= res[1][1]


def test_encoder_index_add_computes_vector_when_absent():
    fake = FakeEncoder({"ram": [3.0, 4.0]})
    idx = vector_index.EncoderVectorIndex(model=fake)
    idx.add("ram")
    res = idx.search(idx.embed("ram"), k=1)
    assert res[0][1] == pytest.approx(1.0)


def test_build_vector_index_lexical_mode():
    idx = vector_index.build_vector_index("lexical")
    assert isinstance(idx, vector_index.LexicalVectorIndex)


def test_build_vector_index_falls_back_when_encoder_unavailable(monkeypatch):
    def _boom(model_name: str):
        raise ImportError("sentence_transformers отсутствует")

    monkeypatch.setattr(vector_index.EncoderVectorIndex, "_load_model", staticmethod(_boom))
    idx = vector_index.build_vector_index("embedding")
    assert isinstance(idx, vector_index.LexicalVectorIndex)


def test_build_vector_index_auto_falls_back_when_encoder_unavailable(monkeypatch):
    def _boom(model_name: str):
        raise OSError("model not found")

    monkeypatch.setattr(vector_index.EncoderVectorIndex, "_load_model", staticmethod(_boom))
    idx = vector_index.build_vector_index("auto")
    assert isinstance(idx, vector_index.LexicalVectorIndex)


def test_build_vector_index_uses_encoder_when_available(monkeypatch):
    fake = FakeEncoder({"ram": [1.0, 0.0]})
    monkeypatch.setattr(
        vector_index.EncoderVectorIndex,
        "_load_model",
        staticmethod(lambda model_name: fake),
    )
    idx = vector_index.build_vector_index("embedding")
    assert isinstance(idx, vector_index.EncoderVectorIndex)

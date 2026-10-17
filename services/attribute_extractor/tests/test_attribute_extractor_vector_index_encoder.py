"""Интеграционный тест семантического VectorIndex на реальной модели.

Отделён от unit-тестов и запускается только при явном флаге, т.к. требует
``sentence-transformers`` и загрузки модели из сети:

    SPECFLOW_RUN_ENCODER_TESTS=1 pytest \
        services/attribute_extractor/tests/test_attribute_extractor_vector_index_encoder.py
"""

from __future__ import annotations

import os

import pytest

from attribute_extractor import vector_index
from attribute_extractor.constants import DEFAULT_EMBEDDING_MODEL

pytestmark = pytest.mark.skipif(
    not os.getenv("SPECFLOW_RUN_ENCODER_TESTS"),
    reason="Семантический индекс: нужен sentence-transformers (флаг SPECFLOW_RUN_ENCODER_TESTS)",
)

pytest.importorskip("sentence_transformers")


def test_encoder_index_matches_russian_synonym() -> None:
    idx = vector_index.EncoderVectorIndex(DEFAULT_EMBEDDING_MODEL)
    idx.add("ram", idx.embed("Оперативная память ; ОЗУ ; RAM"))
    idx.add("processor", idx.embed("Процессор ; CPU ; Chipset"))

    res = idx.search(idx.embed("объём оперативной памяти"), k=2)

    assert res[0][0] == "ram"
    assert res[0][1] > 0.5

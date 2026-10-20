"""Интеграционные тесты PostgresBatchStore с настоящей PostgreSQL.

Отделены от юнит-тестов (AGENTS.md): требуют реального внешнего сервиса и по
умолчанию пропускаются. Запуск локально:

    EXTRACTOR_TEST_DATABASE_URL=postgresql://specflow:specflow@localhost:5432/specflow \
        pytest services/attribute_extractor/tests/ \
            test_attribute_extractor_batch_store_integration.py

Строки используются только в этом тестовом окружении: тест удаляет созданные
записи, чтобы не оставлять мусор в общей базе.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import psycopg
import pytest

from attribute_extractor.batch_store import PostgresBatchStore
from specflow_contracts import BatchExtractResponse, StoredBatchResponse

TEST_DSN = os.environ.get("EXTRACTOR_TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not TEST_DSN, reason="нет EXTRACTOR_TEST_DATABASE_URL (PostgreSQL) — интеграционный тест"
)


def _batch(batch_id: str, *, total: int) -> StoredBatchResponse:
    return StoredBatchResponse(
        batch_id=batch_id,
        created_at=datetime.now(UTC),
        threshold=0.75,
        cards=[{"title": "Кофемолка Bosch TSM6"}],
        response=BatchExtractResponse(total=total, ok=total, low_confidence=0, errors=0),
    )


def test_postgres_store_round_trip() -> None:
    """Полный круг: запись → список → чтение → перезапись тем же batch_id."""
    store = PostgresBatchStore(TEST_DSN)
    batch_id = f"it-batch-{uuid.uuid4()}"
    try:
        store.ensure_schema()
        store.save(_batch(batch_id, total=2))

        loaded = store.get_batch(batch_id)
        assert loaded is not None
        assert loaded.batch_id == batch_id
        assert loaded.response.total == 2
        assert loaded.threshold == 0.75
        assert loaded.cards[0].title == "Кофемолка Bosch TSM6"
        assert loaded.response.persisted is True

        items, total = store.list_batches(limit=100, offset=0)
        assert any(item.batch_id == batch_id for item in items)
        assert total >= 1

        # Повторный batch_id перезаписывает запись (свежая копия побеждает).
        store.save(_batch(batch_id, total=5))
        reloaded = store.get_batch(batch_id)
        assert reloaded is not None
        assert reloaded.response.total == 5

        assert store.get_batch(f"missing-{uuid.uuid4()}") is None
    finally:
        with psycopg.connect(TEST_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM batches WHERE batch_id = %s", (batch_id,))

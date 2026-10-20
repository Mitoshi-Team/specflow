"""Хранилище истории батчей: in-memory реализация и деградация PostgreSQL.

PostgresBatchStore проверяется здесь без реальной БД (правило: юнит-тесты без
внешних сервисов) — на недоступном DSN перевод ошибок драйвера в
``BatchStoreError``. Полный круговой прогон с настоящей PostgreSQL вынесен в
``test_attribute_extractor_batch_store_integration.py`` (интеграционные тесты).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from attribute_extractor.batch_store import (
    BatchStoreError,
    InMemoryBatchStore,
    PostgresBatchStore,
)
from attribute_extractor.constants import IN_MEMORY_BATCH_LIMIT
from specflow_contracts import BatchExtractResponse, StoredBatchResponse

# DSN с закрытым портом: подключение отклоняется мгновенно, реальная БД не нужна.
UNREACHABLE_DSN = "postgresql://nobody:nothing@127.0.0.1:9/postgres?connect_timeout=1"


def _batch(
    batch_id: str,
    *,
    created_at: datetime,
    total: int = 1,
    threshold: float | None = None,
) -> StoredBatchResponse:
    return StoredBatchResponse(
        batch_id=batch_id,
        created_at=created_at,
        threshold=threshold,
        cards=[{"title": "Кофемолка Bosch"}],
        response=BatchExtractResponse(total=total, ok=total, low_confidence=0, errors=0),
    )


# --- InMemoryBatchStore ------------------------------------------------------


def test_in_memory_store_round_trip() -> None:
    """Записанный батч читается без искажений: счётчики, порог, карточки."""
    store = InMemoryBatchStore()
    batch = _batch("b-1", created_at=datetime(2026, 1, 1, tzinfo=UTC), threshold=0.9)

    store.save(batch)

    loaded = store.get_batch("b-1")
    assert loaded is not None
    assert loaded.response.total == 1
    assert loaded.threshold == 0.9
    assert loaded.cards[0].title == "Кофемолка Bosch"


def test_in_memory_store_returns_none_for_unknown_batch() -> None:
    """Неизвестный id — None, а не ошибка: отличает «нет» от сбоя хранилища."""
    assert InMemoryBatchStore().get_batch("missing") is None


def test_in_memory_store_lists_newest_first_with_pagination() -> None:
    """Список новых первыми; limit/offset обрезают страницу, total — общий."""
    store = InMemoryBatchStore()
    store.save(_batch("old", created_at=datetime(2026, 1, 1, tzinfo=UTC)))
    store.save(_batch("mid", created_at=datetime(2026, 1, 2, tzinfo=UTC)))
    store.save(_batch("new", created_at=datetime(2026, 1, 3, tzinfo=UTC)))

    page, total = store.list_batches(limit=2, offset=0)
    assert [item.batch_id for item in page] == ["new", "mid"]
    assert total == 3

    tail, tail_total = store.list_batches(limit=2, offset=2)
    assert [item.batch_id for item in tail] == ["old"]
    assert tail_total == 3


def test_in_memory_store_updates_batch_with_same_id() -> None:
    """Повторный batch_id перезаписывает запись, не плодя дубликаты истории."""
    store = InMemoryBatchStore()
    store.save(_batch("b-1", created_at=datetime(2026, 1, 1, tzinfo=UTC), total=1))
    store.save(_batch("b-1", created_at=datetime(2026, 1, 2, tzinfo=UTC), total=5))

    loaded = store.get_batch("b-1")
    items, total = store.list_batches(limit=10, offset=0)
    assert loaded is not None
    assert loaded.response.total == 5
    assert loaded.created_at == datetime(2026, 1, 2, tzinfo=UTC)
    assert total == 1
    assert [item.batch_id for item in items] == ["b-1"]


def test_in_memory_store_evicts_oldest_beyond_limit() -> None:
    """Переполнение вытесняет самый старый батч — память процесса ограничена."""
    store = InMemoryBatchStore(limit=2)
    for index in range(IN_MEMORY_BATCH_LIMIT):
        store.save(_batch(f"b-{index}", created_at=datetime(2026, 1, 1, tzinfo=UTC)))

    _, total = store.list_batches(limit=10, offset=0)
    assert total == 2
    assert store.get_batch("b-0") is None
    assert store.get_batch(f"b-{IN_MEMORY_BATCH_LIMIT - 1}") is not None


# --- PostgresBatchStore (без реальной БД) -------------------------------------


@pytest.mark.parametrize(
    "operation",
    [
        lambda store: store.ensure_schema(),
        lambda store: store.save(_batch("b-1", created_at=datetime.now(UTC))),
        lambda store: store.list_batches(limit=10, offset=0),
        lambda store: store.get_batch("b-1"),
    ],
    ids=["ensure_schema", "save", "list_batches", "get_batch"],
)
def test_postgres_store_translates_driver_errors(operation) -> None:
    """Сбой подключения к PostgreSQL → BatchStoreError, а не сырой psycopg.Error.

    Таймаут задан в DSN, поэтому тест не зависает даже на чёрной дыре.
    """
    store = PostgresBatchStore(UNREACHABLE_DSN)

    with pytest.raises(BatchStoreError):
        operation(store)


def test_postgres_store_failure_does_not_mark_ready() -> None:
    """После неудачи схема считается не готовой — попытка повторится дальше."""
    store = PostgresBatchStore(UNREACHABLE_DSN)

    with pytest.raises(BatchStoreError):
        store.ensure_schema()

    with pytest.raises(BatchStoreError):
        store.ensure_schema()

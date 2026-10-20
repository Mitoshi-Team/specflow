"""Серверная персистентность выполненных батчей (история результатов).

Замечание ревью: клиент полагался только на localStorage браузера без
серверной сохранности. Здесь батчи сохраняются на сервере (PostgreSQL в
docker-compose) и отдаются через ``GET /api/v1/batches`` (api_contract.md,
4.8/4.9).

Два хранилища с общим протоколом ``BatchStore``:
- ``PostgresBatchStore`` — постоянное хранение, включается ``EXTRACTOR_DATABASE_URL``;
- ``InMemoryBatchStore`` — режим без настроенной БД (dev): история живёт до
  перезапуска процесса и ограничен ``IN_MEMORY_BATCH_LIMIT`` записями.

Гарантия при сбое внешней зависимости: ``BatchStoreError`` не подавляется —
``main`` превращает его либо в признак ``persisted=false`` ответа (запись),
либо в ответ 503 с логом (чтение); извлечение карточек продолжает работать.
"""

import json
from collections import OrderedDict
from typing import Any, Protocol

import psycopg
from psycopg.types.json import Jsonb

from attribute_extractor.constants import (
    BATCH_STORE_CONNECT_TIMEOUT_SECONDS,
    IN_MEMORY_BATCH_LIMIT,
)
from specflow_contracts import (
    BatchExtractResponse,
    BatchSummary,
    ProductCardRequest,
    StoredBatchResponse,
)

_BATCHES_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS batches (
    batch_id   text PRIMARY KEY,
    created_at timestamptz NOT NULL,
    threshold  double precision,
    cards      jsonb NOT NULL,
    response   jsonb NOT NULL
)
"""
# Ключ сортировки в хвосте стабилизирует пагинацию при одинаковом created_at.
_BATCHES_TIME_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS batches_created_at_idx ON batches (created_at DESC, batch_id DESC)"
)


class BatchStoreError(Exception):
    """Сбой хранилища батчей: PostgreSQL недоступна или запрос к ней не прошёл."""


class BatchStore(Protocol):
    """Контракт хранилища истории: запись, чтение, перечисление."""

    def save(self, batch: StoredBatchResponse) -> None:
        """Сохраняет батч; повторный ``batch_id`` перезаписывает запись."""
        ...

    def list_batches(self, limit: int, offset: int) -> tuple[list[BatchSummary], int]:
        """Возвращает страницу сводок (новые первыми) и общее число записей."""
        ...

    def get_batch(self, batch_id: str) -> StoredBatchResponse | None:
        """Возвращает сохранённый батч или ``None``, если он не найден."""
        ...


class InMemoryBatchStore:
    """Хранилище в памяти процесса: dev без PostgreSQL, не переживает рестарт.

    Не является подавлением ошибки: режим выбирается только когда
    ``EXTRACTOR_DATABASE_URL`` не задан, о чём сервис пишет в лог при старте.
    """

    def __init__(self, limit: int = IN_MEMORY_BATCH_LIMIT) -> None:
        self._limit = limit
        # OrderedDict как ограниченная очередь: вставка в конец, вытеснение
        # самого старого элемента при переполнении.
        self._batches: OrderedDict[str, StoredBatchResponse] = OrderedDict()

    def save(self, batch: StoredBatchResponse) -> None:
        # Присвоение существующему ключу сохраняет позицию: повторный
        # batch_id обновляет запись на месте, не меняя порядок истории.
        self._batches[batch.batch_id] = batch
        while len(self._batches) > self._limit:
            self._batches.popitem(last=False)

    def list_batches(self, limit: int, offset: int) -> tuple[list[BatchSummary], int]:
        newest_first = list(reversed(self._batches.values()))
        items = [_to_summary(batch) for batch in newest_first[offset : offset + limit]]
        return items, len(newest_first)

    def get_batch(self, batch_id: str) -> StoredBatchResponse | None:
        return self._batches.get(batch_id)


class PostgresBatchStore:
    """Постоянное хранение батчей в PostgreSQL (psycopg, синхронные запросы).

    Синхронный доступ согласован с пайплайном: он тоже синхронный и уже
    выполняется в цикле событий, а объём запросов невелик (один INSERT на
    батч, один-два SELECT на открытие страницы истории).

    Схема создаётся при первом обращении (``ensure_schema``): если БД лежит на
    старте сервиса, сервис продолжает работать и повторяет попытку дальше —
    самолечение без перезапуска.
    """

    def __init__(self, dsn: str) -> None:
        # DSN может содержать пароль: его нельзя писать в логи, поэтому
        # строка подключения нигде не печатается.
        self._dsn = dsn
        self._ready = False

    def ensure_schema(self) -> None:
        """Создаёт таблицу и индекс истории (идемпотентно); при сбое — BatchStoreError."""
        if self._ready:
            return
        try:
            with psycopg.connect(
                self._dsn, connect_timeout=BATCH_STORE_CONNECT_TIMEOUT_SECONDS
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute(_BATCHES_TABLE_DDL)
                    cur.execute(_BATCHES_TIME_INDEX_DDL)
        except psycopg.Error as exc:
            raise BatchStoreError("не удалось подготовить схему истории батчей") from exc
        self._ready = True

    def _connect(self) -> psycopg.Connection:
        try:
            return psycopg.connect(self._dsn, connect_timeout=BATCH_STORE_CONNECT_TIMEOUT_SECONDS)
        except psycopg.Error as exc:
            raise BatchStoreError("нет подключения к PostgreSQL") from exc

    def save(self, batch: StoredBatchResponse) -> None:
        try:
            self.ensure_schema()
            with self._connect() as conn, conn.cursor() as cur:
                # Повторный batch_id перезаписывает запись (свежая копия
                # батча побеждает — повторный запуск обновляет историю).
                cur.execute(
                    """
                    INSERT INTO batches (batch_id, created_at, threshold, cards, response)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (batch_id) DO UPDATE SET
                        created_at = EXCLUDED.created_at,
                        threshold = EXCLUDED.threshold,
                        cards = EXCLUDED.cards,
                        response = EXCLUDED.response
                    """,
                    (
                        batch.batch_id,
                        batch.created_at,
                        batch.threshold,
                        Jsonb([card.model_dump(mode="json") for card in batch.cards]),
                        Jsonb(batch.response.model_dump(mode="json")),
                    ),
                )
        except psycopg.Error as exc:
            raise BatchStoreError("запись батча в PostgreSQL не удалась") from exc

    def list_batches(self, limit: int, offset: int) -> tuple[list[BatchSummary], int]:
        try:
            self.ensure_schema()
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM batches")
                total = int(cur.fetchone()[0])
                # Счётчики читаются из JSON-ответа, а не дублируются колонками:
                # response — источник истины (api_contract.md, 3.5).
                cur.execute(
                    """
                    SELECT batch_id, created_at, threshold,
                           (response->>'total')::int,
                           (response->>'ok')::int,
                           (response->>'low_confidence')::int,
                           (response->>'errors')::int
                    FROM batches
                    ORDER BY created_at DESC, batch_id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                items = [
                    BatchSummary(
                        batch_id=row[0],
                        created_at=row[1],
                        threshold=row[2],
                        total=row[3],
                        ok=row[4],
                        low_confidence=row[5],
                        errors=row[6],
                    )
                    for row in cur
                ]
        except psycopg.Error as exc:
            raise BatchStoreError("чтение списка батчей из PostgreSQL не удалось") from exc
        return items, total

    def get_batch(self, batch_id: str) -> StoredBatchResponse | None:
        try:
            self.ensure_schema()
            with self._connect() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT batch_id, created_at, threshold, cards, response "
                    "FROM batches WHERE batch_id = %s",
                    (batch_id,),
                )
                row = cur.fetchone()
        except psycopg.Error as exc:
            raise BatchStoreError("чтение батча из PostgreSQL не удалось") from exc
        if row is None:
            return None
        cards = _load_json(row[3])
        return StoredBatchResponse(
            batch_id=row[0],
            created_at=row[1],
            threshold=row[2],
            cards=[ProductCardRequest.model_validate(card) for card in cards],
            response=BatchExtractResponse.model_validate(_load_json(row[4])),
        )


def _to_summary(batch: StoredBatchResponse) -> BatchSummary:
    """Сводка истории из полного сохранённого батча."""
    response = batch.response
    return BatchSummary(
        batch_id=batch.batch_id,
        created_at=batch.created_at,
        threshold=batch.threshold,
        total=response.total,
        ok=response.ok,
        low_confidence=response.low_confidence,
        errors=response.errors,
    )


def _load_json(value: Any) -> Any:
    """Разбирает значение jsonb: psycopg отдаёт его объектом или строкой.

    Тип зависит от загрузчика psycopg, поэтому поддерживаем оба варианта —
    иначе чтение истории падало бы на разных версиях драйвера.
    """
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (str, bytes, bytearray)):
        return json.loads(value)
    raise BatchStoreError(f"неожиданный формат jsonb в истории батчей: {type(value)!r}")

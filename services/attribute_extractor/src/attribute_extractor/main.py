"""Точка входа сервиса извлечения атрибутов (HTTP API — api_contract.md)."""

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from attribute_extractor.batch_store import (
    BatchStore,
    BatchStoreError,
    InMemoryBatchStore,
    PostgresBatchStore,
)
from attribute_extractor.config import Settings
from attribute_extractor.constants import (
    BATCH_LIST_DEFAULT_LIMIT,
    BATCH_LIST_MAX_LIMIT,
    BATCHES_ENDPOINT,
    CATEGORIES_ENDPOINT,
    CATEGORY_LIST_DEFAULT_LIMIT,
    CATEGORY_LIST_MAX_LIMIT,
    CONFIG_ENDPOINT,
    EXTRACT_BATCH_ENDPOINT,
    EXTRACT_ENDPOINT,
    GENERIC_CATEGORY,
    HEALTH_ENDPOINT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE,
    INFO_ENDPOINT,
    NER_EXTRACTOR_NAME,
    RULE_EXTRACTOR_NAME,
)
from attribute_extractor.error_handlers import register_error_handlers
from attribute_extractor.errors import (
    BatchHistoryUnavailableError,
    BatchNotFoundError,
    BatchSizeMismatchError,
    CategoryNotFoundError,
)
from attribute_extractor.extractors import build_default_registry
from attribute_extractor.extractors.registry import ExtractorRegistry
from attribute_extractor.paths import resolve_artifact_path
from attribute_extractor.pipeline import ExtractPipeline
from attribute_extractor.preprocessing import CardPreprocessor, SchemaRegistry, generic_schema
from attribute_extractor.rate_limit import RateLimitMiddleware
from specflow_contracts import (
    BatchExtractRequest,
    BatchExtractResponse,
    BatchListResponse,
    CategorySchema,
    ErrorResponse,
    ExtractionResult,
    ExtractionStatus,
    HealthResponse,
    ProductCardRequest,
    StoredBatchResponse,
)
from specflow_contracts.enums import HealthStatus

logger = logging.getLogger(__name__)

# Коды ошибок, документируемые в OpenAPI для каждого эндпоинта (api_contract.md, 4).
_EXTRACT_RESPONSES: dict[int | str, dict[str, Any]] = {
    HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
}
_BATCH_RESPONSES: dict[int | str, dict[str, Any]] = {
    HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
    HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse},
    HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
}
_CATEGORY_RESPONSES: dict[int | str, dict[str, Any]] = {
    HTTP_404_NOT_FOUND: {"model": ErrorResponse},
}
_BATCH_LIST_RESPONSES: dict[int | str, dict[str, Any]] = {
    HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
}
_BATCH_DETAIL_RESPONSES: dict[int | str, dict[str, Any]] = {
    HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
}


def _persist_batch(
    store: BatchStore,
    request: BatchExtractRequest,
    batch_id: str,
    response: BatchExtractResponse,
) -> bool:
    """Сохраняет батч в серверную историю; ``False`` — запись не удалась (см. лог).

    Сбой хранилища не прерывает запрос: извлечение уже выполнено, клиенту уходит
    признак ``persisted=false``, а traceback причины остаётся в логе сервиса
    (замечание ревью: ошибки записи не должны подавляться молча).
    """
    stored = StoredBatchResponse(
        batch_id=batch_id,
        created_at=datetime.now(UTC),
        threshold=request.threshold_override,
        cards=request.items,
        response=response,
    )
    try:
        store.save(stored)
    except BatchStoreError:
        logger.exception("Не удалось сохранить батч %s в серверной истории", batch_id)
        return False
    return True


def _load_schema_registry(path: str) -> SchemaRegistry:
    """Реестр схем категорий из артефакта ``build_category_schemas.py`` (старт сервиса).

    Отсутствующий или битый артефакт не роняет сервис: причина фиксируется
    в логе, сервис стартует с пустым реестром — карточки получают
    generic-fallback (сценарий «EDA ещё не прогонялся»).
    """
    try:
        registry = SchemaRegistry.from_file(path)
    except FileNotFoundError:
        logger.info("Артефакт схем категорий не найден (%s): generic-fallback", path)
        return SchemaRegistry()
    except Exception:  # noqa: BLE001 — битый артефакт деградирует до generic, но с логом
        logger.exception("Не удалось загрузить реестр схем категорий из %s: generic-fallback", path)
        return SchemaRegistry()
    logger.info("Загружено схем категорий: %d (%s)", len(registry.all()), path)
    return registry


def create_app() -> FastAPI:
    """Собирает и настраивает приложение FastAPI.

    Настройки и пайплайн создаются один раз на приложение; каждый вызов
    фабрики строит свежие ``Settings`` (env-переменные подхватываются
    на момент сборки — это используют тесты деградации).
    """
    app_settings = Settings()
    registry: ExtractorRegistry = build_default_registry(
        ner_model_path=app_settings.ner_model_path,
        ner_span_min_score=app_settings.ner_span_min_score,
        ner_device=app_settings.ner_device,
        match_threshold=app_settings.match_threshold,
    )
    schema_registry = _load_schema_registry(
        str(resolve_artifact_path(app_settings.category_schemas_path))
    )
    pipeline = ExtractPipeline(
        settings=app_settings,
        registry=registry,
        preprocessor=CardPreprocessor(schemas=schema_registry),
    )
    started_at = time.monotonic()

    # Серверная история батчей (api_contract.md, 4.8/4.9): PostgreSQL при
    # заданном EXTRACTOR_DATABASE_URL, иначе память процесса (dev без БД).
    batch_store: BatchStore
    if app_settings.database_url:
        batch_store = PostgresBatchStore(app_settings.database_url)
    else:
        batch_store = InMemoryBatchStore()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Логирует режим истории батчей и заранее готовит схему PostgreSQL."""
        if isinstance(batch_store, PostgresBatchStore):
            logger.info("История батчей: PostgreSQL (EXTRACTOR_DATABASE_URL задан)")
            try:
                batch_store.ensure_schema()
            except BatchStoreError:
                # Сервис не роняем: хранилище повторит подготовку схемы при
                # первом обращении, причина зафиксирована здесь с traceback.
                logger.exception("Схема истории батчей не создана при старте сервиса")
        else:
            logger.info(
                "История батчей: память процесса (EXTRACTOR_DATABASE_URL не задан) "
                "— данные не переживают перезапуск"
            )
        yield

    app = FastAPI(
        title=app_settings.app_name, docs_url="/docs", redoc_url="/redoc", lifespan=lifespan
    )
    # Хранилище доступно через state: тесты подменяют его на заглушки.
    app.state.batch_store = batch_store

    def _current_store() -> BatchStore:
        """Актуальное хранилище истории батчей (чтение на момент запроса)."""
        return cast(BatchStore, app.state.batch_store)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Глобальная трансляция исключений в ErrorResponse (api_contract.md, 3.8).
    register_error_handlers(app)
    if app_settings.rate_limit_requests > 0:
        # /health не лимитируется: его дёшево и часто пингуют healthcheck'и.
        app.add_middleware(
            RateLimitMiddleware,
            requests=app_settings.rate_limit_requests,
            window_seconds=app_settings.rate_limit_window_seconds,
            exclude_paths={f"{app_settings.api_prefix}{HEALTH_ENDPOINT}"},
        )

    @app.post(
        f"{app_settings.api_prefix}{EXTRACT_ENDPOINT}",
        response_model=ExtractionResult,
        responses=_EXTRACT_RESPONSES,
        tags=["extract"],
    )
    async def extract(request: ProductCardRequest) -> ExtractionResult:
        """Извлечение атрибутов для одной карточки.

        Ошибки транслируются глобальными обработчиками: нарушение инварианта
        очистки → 500 invariant_violation, прочие сбои → 500 internal_error
        (api_contract.md, 4.1).
        """
        return pipeline.extract(request)

    @app.post(
        f"{app_settings.api_prefix}{EXTRACT_BATCH_ENDPOINT}",
        response_model=BatchExtractResponse,
        responses=_BATCH_RESPONSES,
        tags=["extract"],
    )
    async def extract_batch(request: BatchExtractRequest) -> BatchExtractResponse:
        """Пакетное извлечение с частичным успехом по каждой карточке."""
        if request.batch_size is not None and request.batch_size != len(request.items):
            # Несогласованный запрос → 400 (api_contract.md, 4.2).
            raise BatchSizeMismatchError(request.batch_size, len(request.items))
        started = time.monotonic()
        results: list[ExtractionResult] = []
        for index, item in enumerate(request.items):
            try:
                # threshold_override — локальное переопределение порога для
                # этого запроса; Settings не мутирует (задача 1.2).
                results.append(
                    pipeline.extract(item, confidence_threshold=request.threshold_override)
                )
            except Exception:
                # Ошибка одной карточки не прерывает батч (частичный успех);
                # причина фиксируется в логе с traceback (api_contract.md, 5).
                logger.exception(
                    "Extraction failed for item %d (product_id=%s)",
                    index,
                    item.product_id,
                )
                results.append(
                    ExtractionResult(
                        attributes=[],
                        status=ExtractionStatus.ERROR,
                        needs_review=True,
                        pipeline_version=app_settings.pipeline_version,
                        product_id=item.product_id,
                        category_id=item.category_id,
                        category_name=item.category_name,
                        low_confidence_count=0,
                        processing_time_ms=0,
                    )
                )
        batch_id = request.batch_id or str(uuid.uuid4())
        # Батч считается сохранённым: при неудаче записи ниже признак
        # инвертируется, а копия в истории (если запись прошла) остаётся
        # с persisted=true — клиент видит честное состояние.
        response = BatchExtractResponse(
            batch_id=batch_id,
            total=len(results),
            ok=sum(result.status == ExtractionStatus.OK for result in results),
            low_confidence=sum(
                result.status == ExtractionStatus.LOW_CONFIDENCE for result in results
            ),
            errors=sum(result.status == ExtractionStatus.ERROR for result in results),
            results=results,
            processing_time_ms_total=int((time.monotonic() - started) * 1000),
            persisted=True,
        )
        if not _persist_batch(_current_store(), request, batch_id, response):
            response.persisted = False
        return response

    @app.get(
        f"{app_settings.api_prefix}{BATCHES_ENDPOINT}",
        response_model=BatchListResponse,
        responses=_BATCH_LIST_RESPONSES,
        tags=["batches"],
    )
    async def batches(
        limit: int = Query(BATCH_LIST_DEFAULT_LIMIT, ge=1, le=BATCH_LIST_MAX_LIMIT),
        offset: int = Query(0, ge=0),
    ) -> BatchListResponse:
        """История сохранённых батчей, новые первыми (api_contract.md, 4.8).

        Хранилище недоступно → 503 ErrorResponse; извлечение при этом
        продолжает работать (замечание ревью: сбои внешних зависимостей
        должны быть видны, а не подавлены).
        """
        try:
            items, total = _current_store().list_batches(limit=limit, offset=offset)
        except BatchStoreError as exc:
            logger.exception(
                "Не удалось получить список батчей (limit=%d, offset=%d)", limit, offset
            )
            raise BatchHistoryUnavailableError from exc
        return BatchListResponse(items=items, total=total)

    @app.get(
        f"{app_settings.api_prefix}{BATCHES_ENDPOINT}/{{batch_id}}",
        response_model=StoredBatchResponse,
        responses=_BATCH_DETAIL_RESPONSES,
        tags=["batches"],
    )
    async def batch_detail(batch_id: str) -> StoredBatchResponse:
        """Сохранённый батч: 404 — не найден, 503 — хранилище недоступно (4.9)."""
        try:
            stored = _current_store().get_batch(batch_id)
        except BatchStoreError as exc:
            logger.exception("Не удалось прочитать батч %s из истории", batch_id)
            raise BatchHistoryUnavailableError from exc
        if stored is None:
            raise BatchNotFoundError(batch_id)
        return stored

    @app.get(f"{app_settings.api_prefix}{CATEGORIES_ENDPOINT}", tags=["categories"])
    async def categories(
        category: str | None = None,
        limit: int = Query(CATEGORY_LIST_DEFAULT_LIMIT, ge=0, le=CATEGORY_LIST_MAX_LIMIT),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        """Список зарегистрированных схем категорий плюс generic-схема.

        Реестр загружается на старте из ``category_schemas_path`` (артефакт
        ``scripts/build_category_schemas.py``); при пустом реестре отдаётся
        только generic-схема. ``category`` фильтрует по имени
        (регистронезависимо), пагинация — limit/offset (api_contract.md, 4.3).
        """
        items = [generic_schema().model_dump(), *(s.model_dump() for s in schema_registry.all())]
        if category is not None:
            wanted = category.strip().casefold()
            items = [item for item in items if item["category"].strip().casefold() == wanted]
        return {"items": items[offset : offset + limit], "total": len(items)}

    @app.get(
        f"{app_settings.api_prefix}{CATEGORIES_ENDPOINT}/{{category}}",
        response_model=CategorySchema,
        responses=_CATEGORY_RESPONSES,
        tags=["categories"],
    )
    async def category_detail(category: str) -> CategorySchema:
        """Схема категории из реестра; generic-схема либо 404 ErrorResponse."""
        schema = schema_registry.get(category_name=category)
        if schema is not None:
            return schema
        if category == GENERIC_CATEGORY:
            return generic_schema()
        raise CategoryNotFoundError(category)

    def _health_models() -> tuple[list[str], bool]:
        """Загруженные компоненты и доступность rules по текущим настройкам."""
        models_loaded: list[str] = []
        if app_settings.enable_rules and registry.get(RULE_EXTRACTOR_NAME) is not None:
            models_loaded.append("rules")
        if app_settings.enable_vector_match:
            models_loaded.append("vector_index")
        ner = registry.get(NER_EXTRACTOR_NAME)
        if ner is not None and ner.is_available():
            models_loaded.append("ner")
        return models_loaded, "rules" in models_loaded

    @app.get(
        f"{app_settings.api_prefix}{HEALTH_ENDPOINT}",
        response_model=HealthResponse,
        tags=["health"],
    )
    async def health() -> HealthResponse:
        """Проверка работоспособности (api_contract.md, 3.7).

        Штатный режим сегодня — degraded: rules работают, NER-модель и
        векторный индекс не загружены.
        """
        models_loaded, rules_available = _health_models()
        if not rules_available:
            # Базовый пайплайн недоступен — критическая ошибка инициализации.
            status = HealthStatus.DOWN
        elif {"rules", "ner", "vector_index"} <= set(models_loaded):
            status = HealthStatus.OK
        else:
            status = HealthStatus.DEGRADED
        return HealthResponse(
            status=status,
            version=app_settings.service_version,
            pipeline_version=app_settings.pipeline_version,
            models_loaded=models_loaded,
            uptime_seconds=int(time.monotonic() - started_at),
        )

    @app.get(f"{app_settings.api_prefix}{INFO_ENDPOINT}", tags=["info"])
    async def info() -> dict[str, Any]:
        """Информация о сервисе (api_contract.md, 4.6)."""
        return {
            "service_name": "attribute-extractor",
            "version": app_settings.service_version,
            "pipeline_version": app_settings.pipeline_version,
            "extraction_methods": [RULE_EXTRACTOR_NAME, NER_EXTRACTOR_NAME],
            "default_threshold": app_settings.default_confidence_threshold,
            "supports_batch": True,
            "max_batch_size": app_settings.max_batch_size,
            "text_only": True,
            "features": {
                "grounding_required": app_settings.grounding_required,
                "normalization": app_settings.normalization_enabled,
                "unit_conversion": app_settings.unit_conversion_enabled,
                # Взвешивание по трафику отложено (задача 3).
                "traffic_weighted_metrics": False,
            },
        }

    @app.get(f"{app_settings.api_prefix}{CONFIG_ENDPOINT}", tags=["config"])
    async def config() -> dict[str, Any]:
        """Текущие пороги (read-only, без секретов) — api_contract.md, 4.7."""
        return {
            "confidence_thresholds": {
                "auto": app_settings.default_confidence_threshold,
                "review": app_settings.review_confidence_threshold,
            },
            "match_threshold": app_settings.match_threshold,
            "deterministic_confidence": app_settings.deterministic_confidence,
        }

    return app


app = create_app()

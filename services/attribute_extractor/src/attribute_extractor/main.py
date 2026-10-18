"""Точка входа сервиса извлечения атрибутов (HTTP API — api_contract.md)."""

import time
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from attribute_extractor.config import Settings
from attribute_extractor.constants import (
    CATEGORIES_ENDPOINT,
    CATEGORY_LIST_DEFAULT_LIMIT,
    CATEGORY_LIST_MAX_LIMIT,
    CONFIG_ENDPOINT,
    DEFAULT_DETERMINISTIC_CONFIDENCE,
    EXTRACT_BATCH_ENDPOINT,
    EXTRACT_ENDPOINT,
    GENERIC_CATEGORY,
    HEALTH_ENDPOINT,
    INFO_ENDPOINT,
    NER_EXTRACTOR_NAME,
    RULE_EXTRACTOR_NAME,
)
from attribute_extractor.extractors import build_default_registry
from attribute_extractor.extractors.registry import ExtractorRegistry
from attribute_extractor.pipeline import ExtractPipeline
from attribute_extractor.preprocessing import generic_schema
from specflow_contracts import (
    BatchExtractRequest,
    BatchExtractResponse,
    CategorySchema,
    ExtractionResult,
    ExtractionStatus,
    HealthResponse,
    ProductCardRequest,
)
from specflow_contracts.enums import HealthStatus


def create_app() -> FastAPI:
    """Собирает и настраивает приложение FastAPI.

    Настройки и пайплайн создаются один раз на приложение; каждый вызов
    фабрики строит свежие ``Settings`` (env-переменные подхватываются
    на момент сборки — это используют тесты деградации).
    """
    app_settings = Settings()
    registry: ExtractorRegistry = build_default_registry()
    pipeline = ExtractPipeline(settings=app_settings, registry=registry)
    started_at = time.monotonic()

    app = FastAPI(title=app_settings.app_name, docs_url="/docs", redoc_url="/redoc")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post(
        f"{app_settings.api_prefix}{EXTRACT_ENDPOINT}",
        response_model=ExtractionResult,
        tags=["extract"],
    )
    async def extract(request: ProductCardRequest) -> ExtractionResult:
        """Извлечение атрибутов для одной карточки."""
        try:
            return pipeline.extract(request)
        except ValueError:
            # Нарушение инварианта очистки текста (Этап 0) → ErrorResponse.
            raise HTTPException(status_code=500, detail="text cleanup invariant violated") from None
        except Exception:
            raise HTTPException(status_code=500, detail="internal server error") from None

    @app.post(
        f"{app_settings.api_prefix}{EXTRACT_BATCH_ENDPOINT}",
        response_model=BatchExtractResponse,
        tags=["extract"],
    )
    async def extract_batch(request: BatchExtractRequest) -> BatchExtractResponse:
        """Пакетное извлечение с частичным успехом по каждой карточке."""
        started = time.monotonic()
        results: list[ExtractionResult] = []
        for item in request.items:
            try:
                # threshold_override — локальное переопределение порога для
                # этого запроса; Settings не мутирует (задача 1.2).
                results.append(
                    pipeline.extract(item, confidence_threshold=request.threshold_override)
                )
            except Exception:
                # Ошибка одной карточки не прерывает батч (частичный успех).
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
        return BatchExtractResponse(
            batch_id=request.batch_id,
            total=len(results),
            ok=sum(result.status == ExtractionStatus.OK for result in results),
            low_confidence=sum(
                result.status == ExtractionStatus.LOW_CONFIDENCE for result in results
            ),
            errors=sum(result.status == ExtractionStatus.ERROR for result in results),
            results=results,
            processing_time_ms_total=int((time.monotonic() - started) * 1000),
        )

    @app.get(f"{app_settings.api_prefix}{CATEGORIES_ENDPOINT}", tags=["categories"])
    async def categories(
        category: str | None = None,
        limit: int = Query(CATEGORY_LIST_DEFAULT_LIMIT, ge=0, le=CATEGORY_LIST_MAX_LIMIT),
        offset: int = Query(0, ge=0),
    ) -> dict[str, Any]:
        """Список зарегистрированных схем категорий.

        Реестр схем пока пуст: отдаётся только generic-схема (придумывать
        фейковые схемы нельзя — задача 1.3).
        """
        known = category in (None, GENERIC_CATEGORY)
        items = [generic_schema().model_dump()] if known else []
        return {"items": items[offset : offset + limit], "total": len(items)}

    @app.get(
        f"{app_settings.api_prefix}{CATEGORIES_ENDPOINT}/{{category}}",
        response_model=CategorySchema,
        tags=["categories"],
    )
    async def category_detail(category: str) -> CategorySchema:
        """Схема категории; 404 ErrorResponse, если не найдена."""
        if category == GENERIC_CATEGORY:
            return generic_schema()
        raise HTTPException(status_code=404, detail="category not found")

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
            "deterministic_confidence": DEFAULT_DETERMINISTIC_CONFIDENCE,
        }

    return app


app = create_app()

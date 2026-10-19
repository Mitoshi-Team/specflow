"""Точка входа API Gateway."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api_gateway.config import settings
from api_gateway.constants import HEALTH_ENDPOINT
from api_gateway.proxy import register_proxy


def create_app(upstream_transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    """Собирает и настраивает приложение FastAPI.

    Вынесено в фабрику, чтобы приложение можно было создавать в тестах
    с изолированными настройками. ``upstream_transport`` подменяет транспорт
    httpx (например, ``httpx.MockTransport``) в тестах проксирования.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Держит один HTTP-клиент к сервису извлечения на время жизни процесса."""
        timeout = httpx.Timeout(
            settings.upstream_timeout_seconds,
            connect=settings.upstream_connect_timeout_seconds,
        )
        async with httpx.AsyncClient(timeout=timeout, transport=upstream_transport) as client:
            app.state.upstream_client = client
            yield

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get(f"{settings.api_prefix}{HEALTH_ENDPOINT}", tags=["health"])
    async def health() -> dict[str, str]:
        """Проверка работоспособности шлюза (liveness, в upstream не проксируется)."""
        return {"status": "ok"}

    # Публичные маршруты извлечения проксируются в attribute_extractor
    # (architecture.md: логики извлечения в шлюзе нет). Регистрируется после
    # /health, чтобы явный маршрут имел приоритет над catch-all.
    register_proxy(
        app,
        base_url=settings.attribute_extractor_url,
        prefix=settings.api_prefix,
    )

    return app


app = create_app()

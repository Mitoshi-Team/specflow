"""Точка входа API Gateway."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api_gateway.config import settings
from api_gateway.constants import HEALTH_ENDPOINT


def create_app() -> FastAPI:
    """Собирает и настраивает приложение FastAPI.

    Вынесено в фабрику, чтобы приложение можно было создавать в тестах
    с изолированными настройками.
    """
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get(f"{settings.api_prefix}{HEALTH_ENDPOINT}", tags=["health"])
    async def health() -> dict[str, str]:
        """Проверка работоспособности сервиса."""
        return {"status": "ok"}

    return app


app = create_app()

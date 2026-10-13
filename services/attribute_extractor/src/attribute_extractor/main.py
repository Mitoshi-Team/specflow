"""Точка входа сервиса извлечения атрибутов."""

from fastapi import FastAPI

from attribute_extractor.config import settings
from attribute_extractor.constants import HEALTH_ENDPOINT


def create_app() -> FastAPI:
    """Собирает и настраивает приложение FastAPI."""
    app = FastAPI(title=settings.app_name)

    @app.get(f"{settings.api_prefix}{HEALTH_ENDPOINT}", tags=["health"])
    async def health() -> dict[str, str]:
        """Проверка работоспособности сервиса."""
        return {"status": "ok"}

    return app


app = create_app()

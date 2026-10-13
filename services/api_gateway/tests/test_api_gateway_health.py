from fastapi.testclient import TestClient

from api_gateway.config import settings
from api_gateway.constants import HEALTH_ENDPOINT
from api_gateway.main import app


def test_health_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get(f"{settings.api_prefix}{HEALTH_ENDPOINT}")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

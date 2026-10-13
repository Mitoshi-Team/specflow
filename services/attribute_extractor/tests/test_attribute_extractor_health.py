from fastapi.testclient import TestClient

from attribute_extractor.config import settings
from attribute_extractor.constants import HEALTH_ENDPOINT
from attribute_extractor.main import app


def test_health_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get(f"{settings.api_prefix}{HEALTH_ENDPOINT}")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

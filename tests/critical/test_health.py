import pytest
from fastapi.testclient import TestClient

from app.presentation.main import app


@pytest.mark.critical
def test_health_endpoint_returns_ok() -> None:
    client = TestClient(app)
    response = client.get('/api/health')

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert payload['service'] == 'docere-service'

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.infrastructure.settings import clear_settings_cache, get_settings
from app.presentation.main import create_app


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('APP_DATABASE__URL', 'postgresql+psycopg://docere:docere@localhost:5432/docere')
    monkeypatch.setenv('APP_AUTH__SECRET_KEY', 'test-secret-key-32-bytes-minimum-0001')
    monkeypatch.setenv('APP_STORAGE__ENDPOINT', 'http://localhost:9000')
    monkeypatch.setenv('APP_STORAGE__BUCKET', 'docere-records')
    monkeypatch.setenv('APP_QUEUE__BROKER_URL', 'redis://localhost:6379/0')


@pytest.mark.critical
def test_app_starts_with_full_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    clear_settings_cache()

    with TestClient(create_app()) as client:
        response = client.get('/api/health')

    assert response.status_code == 200


@pytest.mark.critical
def test_app_start_fails_without_required_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv('APP_DATABASE__URL', raising=False)
    clear_settings_cache()

    with pytest.raises(ValidationError), TestClient(create_app()):
        pass


@pytest.mark.critical
def test_missing_db_url_returns_clear_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv('APP_DATABASE__URL', raising=False)
    clear_settings_cache()

    with pytest.raises(ValidationError) as exc_info:
        get_settings()

    error_text = str(exc_info.value).lower()
    assert 'database' in error_text
    assert 'field required' in error_text

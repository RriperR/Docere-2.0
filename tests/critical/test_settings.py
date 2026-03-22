from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.infrastructure.config.paths import find_project_root
from app.infrastructure.config.settings import clear_settings_cache, get_settings
from app.presentation.main import create_app


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('APP_DATABASE__URL', 'postgresql+psycopg://docere:docere@localhost:5432/docere')
    monkeypatch.setenv('APP_AUTH__SECRET_KEY', 'test-secret-key-32-bytes-minimum-0001')
    monkeypatch.setenv('APP_STORAGE__ENDPOINT', 'http://localhost:9000')
    monkeypatch.setenv('APP_STORAGE__BUCKET', 'docere-records')
    monkeypatch.setenv('APP_QUEUE__BROKER_URL', 'redis://localhost:6379/0')


def _clear_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('APP_DATABASE__URL', raising=False)
    monkeypatch.delenv('APP_AUTH__SECRET_KEY', raising=False)
    monkeypatch.delenv('APP_STORAGE__ENDPOINT', raising=False)
    monkeypatch.delenv('APP_STORAGE__BUCKET', raising=False)
    monkeypatch.delenv('APP_QUEUE__BROKER_URL', raising=False)


@pytest.mark.critical
def test_app_starts_with_full_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    clear_settings_cache()

    with TestClient(create_app(env_file=None)) as client:
        response = client.get('/api/health')

    assert response.status_code == 200


@pytest.mark.critical
def test_app_start_fails_without_required_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv('APP_DATABASE__URL', raising=False)
    clear_settings_cache()

    with pytest.raises(ValidationError), TestClient(create_app(env_file=None)):
        pass


@pytest.mark.critical
def test_missing_db_url_returns_clear_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv('APP_DATABASE__URL', raising=False)
    clear_settings_cache()

    with pytest.raises(ValidationError) as exc_info:
        get_settings(env_file=None)

    error_text = str(exc_info.value).lower()
    assert 'database' in error_text
    assert 'field required' in error_text


@pytest.mark.critical
def test_settings_can_be_loaded_from_explicit_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_required_env(monkeypatch)
    env_file = tmp_path / '.env.test'
    env_file.write_text(
        '\n'.join(
            [
                'APP_DATABASE__URL=postgresql+psycopg://docere:docere@localhost:5432/docere',
                'APP_AUTH__SECRET_KEY=dotenv-secret-key',
                'APP_STORAGE__ENDPOINT=http://localhost:9000',
                'APP_STORAGE__BUCKET=docere-records',
                'APP_QUEUE__BROKER_URL=redis://localhost:6379/0',
            ]
        ),
        encoding='utf-8',
    )
    clear_settings_cache()

    settings = get_settings(env_file=env_file)

    assert settings.database.url == 'postgresql+psycopg://docere:docere@localhost:5432/docere'
    assert settings.auth.secret_key.get_secret_value() == 'dotenv-secret-key'


@pytest.mark.critical
def test_environment_variables_override_dotenv_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _clear_required_env(monkeypatch)
    env_file = tmp_path / '.env.test'
    env_file.write_text(
        '\n'.join(
            [
                'APP_DATABASE__URL=postgresql+psycopg://docere:docere@localhost:5432/from-dotenv',
                'APP_AUTH__SECRET_KEY=dotenv-secret-key',
                'APP_STORAGE__ENDPOINT=http://localhost:9000',
                'APP_STORAGE__BUCKET=docere-records',
                'APP_QUEUE__BROKER_URL=redis://localhost:6379/0',
            ]
        ),
        encoding='utf-8',
    )
    monkeypatch.setenv('APP_DATABASE__URL', 'postgresql+psycopg://docere:docere@localhost:5432/from-env')
    clear_settings_cache()

    settings = get_settings(env_file=env_file)

    assert settings.database.url == 'postgresql+psycopg://docere:docere@localhost:5432/from-env'


@pytest.mark.critical
def test_project_root_can_be_resolved_without_pyproject(tmp_path: Path) -> None:
    config_dir = tmp_path / 'src' / 'app' / 'infrastructure' / 'config'
    config_dir.mkdir(parents=True)

    project_root = find_project_root(config_dir)

    assert project_root == tmp_path

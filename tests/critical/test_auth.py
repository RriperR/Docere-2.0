from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.user import UserRow
from app.infrastructure.db.session import clear_db_session_cache, get_engine, get_session_factory
from app.infrastructure.settings import clear_settings_cache
from app.presentation.main import create_app


def _set_required_auth_env(monkeypatch: pytest.MonkeyPatch, sqlite_path: Path) -> None:
    monkeypatch.setenv('APP_DATABASE__URL', f'sqlite+pysqlite:///{sqlite_path.as_posix()}')
    monkeypatch.setenv('APP_AUTH__SECRET_KEY', 'test-secret-key-32-bytes-minimum-0001')
    monkeypatch.setenv('APP_AUTH__ACCESS_TOKEN_TTL_MINUTES', '60')
    monkeypatch.setenv('APP_AUTH__REFRESH_TOKEN_TTL_MINUTES', '10080')
    monkeypatch.setenv('APP_AUTH__JWT_ALGORITHM', 'HS256')
    monkeypatch.setenv('APP_STORAGE__ENDPOINT', 'http://localhost:9000')
    monkeypatch.setenv('APP_STORAGE__BUCKET', 'docere-records')
    monkeypatch.setenv('APP_QUEUE__BROKER_URL', 'redis://localhost:6379/0')
    monkeypatch.setenv('APP_QUEUE__RESULT_BACKEND', 'redis://localhost:6379/1')


@pytest.fixture
def auth_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    sqlite_path = tmp_path / 'auth.sqlite3'
    _set_required_auth_env(monkeypatch, sqlite_path)
    clear_settings_cache()
    clear_db_session_cache()
    Base.metadata.create_all(bind=get_engine())

    with TestClient(create_app()) as client:
        yield client

    clear_db_session_cache()
    clear_settings_cache()


def _build_registration_payload() -> dict[str, str]:
    return {
        'fio': 'Иванов Иван Иванович',
        'email': 'Patient@example.com',
        'phone': '+79990000000',
        'password': 'VeryStrongPass123',
        'date_of_birth': '1990-01-01',
    }


@pytest.mark.critical
def test_register_stores_hashed_password(auth_client: TestClient) -> None:
    payload = _build_registration_payload()

    response = auth_client.post('/api/auth/register', json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body['role'] == 'patient'
    assert body['email'] == 'patient@example.com'
    assert 'password' not in body

    with get_session_factory()() as session:
        user = session.scalar(select(UserRow).where(UserRow.email == 'patient@example.com'))

    assert user is not None
    assert user.password_hash != payload['password']
    assert user.password_hash.startswith('pbkdf2_sha256$')


@pytest.mark.critical
def test_register_rejects_duplicate_email(auth_client: TestClient) -> None:
    payload = _build_registration_payload()

    first_response = auth_client.post('/api/auth/register', json=payload)
    assert first_response.status_code == 201

    second_response = auth_client.post('/api/auth/register', json=payload)
    assert second_response.status_code == 409
    assert second_response.json()['detail'] == 'User with this email already exists'


@pytest.mark.critical
def test_register_requires_mandatory_fields(auth_client: TestClient) -> None:
    payload = _build_registration_payload()
    payload.pop('phone')

    response = auth_client.post('/api/auth/register', json=payload)

    assert response.status_code == 422


@pytest.mark.critical
def test_login_returns_access_token(auth_client: TestClient) -> None:
    payload = _build_registration_payload()
    register_response = auth_client.post('/api/auth/register', json=payload)
    assert register_response.status_code == 201

    login_response = auth_client.post(
        '/api/auth/login',
        json={'email': payload['email'], 'password': payload['password']},
    )

    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload['token_type'] == 'bearer'  # noqa: S105
    assert isinstance(login_payload['access_token'], str)
    assert login_payload['access_token']
    assert isinstance(login_payload['refresh_token'], str)
    assert login_payload['refresh_token']


@pytest.mark.critical
def test_refresh_returns_new_token_pair(auth_client: TestClient) -> None:
    payload = _build_registration_payload()
    register_response = auth_client.post('/api/auth/register', json=payload)
    assert register_response.status_code == 201

    login_response = auth_client.post(
        '/api/auth/login',
        json={'email': payload['email'], 'password': payload['password']},
    )
    assert login_response.status_code == 200
    refresh_token = login_response.json()['refresh_token']

    refresh_response = auth_client.post('/api/auth/refresh', json={'refresh_token': refresh_token})

    assert refresh_response.status_code == 200
    refresh_payload = refresh_response.json()
    assert refresh_payload['token_type'] == 'bearer'  # noqa: S105
    assert refresh_payload['access_token']
    assert refresh_payload['refresh_token']


@pytest.mark.critical
def test_refresh_rejects_access_token(auth_client: TestClient) -> None:
    payload = _build_registration_payload()
    register_response = auth_client.post('/api/auth/register', json=payload)
    assert register_response.status_code == 201

    login_response = auth_client.post(
        '/api/auth/login',
        json={'email': payload['email'], 'password': payload['password']},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()['access_token']

    refresh_response = auth_client.post('/api/auth/refresh', json={'refresh_token': access_token})

    assert refresh_response.status_code == 401
    assert refresh_response.json()['detail'] == 'Invalid or expired refresh token'


@pytest.mark.critical
def test_protected_endpoint_requires_valid_token(auth_client: TestClient) -> None:
    payload = _build_registration_payload()
    register_response = auth_client.post('/api/auth/register', json=payload)
    assert register_response.status_code == 201

    login_response = auth_client.post(
        '/api/auth/login',
        json={'email': payload['email'], 'password': payload['password']},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()['access_token']
    refresh_token = login_response.json()['refresh_token']

    valid_response = auth_client.get('/api/auth/me', headers={'Authorization': f'Bearer {access_token}'})
    assert valid_response.status_code == 200
    assert valid_response.json()['email'] == 'patient@example.com'

    invalid_response = auth_client.get('/api/auth/me', headers={'Authorization': 'Bearer broken-token'})
    assert invalid_response.status_code == 401

    refresh_as_access_response = auth_client.get('/api/auth/me', headers={'Authorization': f'Bearer {refresh_token}'})
    assert refresh_as_access_response.status_code == 401

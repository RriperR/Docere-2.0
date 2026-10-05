"""Общие API-фикстуры с изолированной БД для критических сценариев."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_records import _set_required_env
from test_records import record_client as record_client

from app.infrastructure.config.settings import clear_settings_cache
from app.infrastructure.db.base import Base
from app.infrastructure.db.session import clear_db_session_cache, get_engine
from app.presentation.main import create_app
from app.presentation.webserver.rate_limit import clear_auth_rate_limits


@pytest.fixture
def postgres_case_client(monkeypatch, tmp_path):
    """Изолировать реальные конкурентные API-запросы в отдельной схеме PostgreSQL."""
    url = os.environ.get('DOCERE_TEST_POSTGRES_URL')
    if not url:
        pytest.skip('Requires isolated PostgreSQL')
    schema = 'case_test_' + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
    scoped_url = (
        make_url(url).update_query_dict({'options': f'-csearch_path={schema}'}).render_as_string(hide_password=False)
    )
    _set_required_env(monkeypatch, tmp_path / 'unused.sqlite')
    monkeypatch.setenv('APP_DATABASE__URL', scoped_url)
    clear_settings_cache()
    clear_db_session_cache()
    clear_auth_rate_limits()
    try:
        Base.metadata.create_all(get_engine())
        with TestClient(create_app()) as client:
            yield client
    finally:
        clear_db_session_cache()
        clear_settings_cache()
        clear_auth_rate_limits()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()

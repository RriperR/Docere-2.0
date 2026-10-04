"""Проверка реальных миграций и сохранности legacy-данных в отдельной схеме PostgreSQL."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

pytestmark = [
    pytest.mark.critical,
    pytest.mark.skipif(not os.environ.get('DOCERE_TEST_POSTGRES_URL'), reason='Requires isolated PostgreSQL'),
]


def test_upgrade_downgrade_matches_models_and_preserves_legacy_authorship(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ['DOCERE_TEST_POSTGRES_URL']
    schema = f'test_migrations_{uuid4().hex}'
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA {schema}'))
    scoped_url = (
        make_url(url).update_query_dict({'options': f'-csearch_path={schema}'}).render_as_string(hide_password=False)
    )
    monkeypatch.setenv('APP_DATABASE__URL', scoped_url)
    engine = create_engine(scoped_url)
    config = Config(str(Path(__file__).resolve().parents[2] / 'alembic.ini'))
    ids = {key: uuid4() for key in ('user', 'patient', 'record', 'file')}
    try:
        command.upgrade(config, '20261004_17')
        with engine.begin() as connection:
            connection.execute(
                text(
                    'INSERT INTO users (id,fio,email,phone,password_hash,role,status) '
                    "VALUES (:user,'Synthetic','legacy@example.com','+79990000000','test','doctor','active')"
                ),
                ids,
            )
            connection.execute(
                text("INSERT INTO patient_passports (id,fio,status) VALUES (:patient,'Legacy patient','draft')"),
                ids,
            )
            connection.execute(
                text(
                    'INSERT INTO medical_records (id,creator_user_id,status,record_type,event_date,payload_json) '
                    "VALUES (:record,:user,'unconfirmed','other','2026-10-05','{\"legacy\": true}')"
                ),
                ids,
            )
            connection.execute(
                text(
                    'INSERT INTO file_attachments (id,record_id,category,storage_key,mime_type,size_bytes) '
                    "VALUES (:file,:record,'document','legacy/report.txt','text/plain',42)"
                ),
                ids,
            )
        command.upgrade(config, 'head')
        command.check(config)  # Types, defaults, nullability, indexes and constraints must all agree.
        with engine.connect() as connection:
            assert connection.scalar(text('SELECT created_by_user_id FROM patient_passports')) is None
            assert connection.scalar(text('SELECT uploaded_by_user_id FROM file_attachments')) is None
            assert connection.scalar(text('SELECT payload_json FROM medical_records')) == {'legacy': True}
        command.downgrade(config, '20261004_17')
        assert 'ix_medical_records_creator_user_id' not in {
            index['name'] for index in inspect(engine).get_indexes('medical_records')
        }
        command.upgrade(config, 'head')
        command.check(config)
        with engine.connect() as connection:
            assert connection.scalar(text('SELECT COUNT(*) FROM file_attachments')) == 1
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()

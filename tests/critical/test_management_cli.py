"""Критические тесты management CLI."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest
from sqlalchemy import func, select

from app.infrastructure.config.settings import clear_settings_cache
from app.infrastructure.db.base import Base
from app.infrastructure.db.models.auth.user import UserRow
from app.infrastructure.db.models.medical_records.medical_record import MedicalRecordRow
from app.infrastructure.db.session import clear_db_session_cache, get_engine, get_session_factory
from app.presentation.cli import main


def _set_required_env(monkeypatch: pytest.MonkeyPatch, sqlite_path: Path) -> None:
    """Подготовить минимальный набор переменных окружения для CLI-тестов.

    Args:
        monkeypatch: Инструмент подмены переменных окружения в тесте.
        sqlite_path: Путь к SQLite-файлу тестовой базы.
    """
    monkeypatch.setenv('APP_DATABASE__URL', f'sqlite+pysqlite:///{sqlite_path.as_posix()}')
    monkeypatch.setenv('APP_AUTH__SECRET_KEY', 'test-secret-key-32-bytes-minimum-0001')
    monkeypatch.setenv('APP_STORAGE__ENDPOINT', 'http://localhost:9000')
    monkeypatch.setenv('APP_STORAGE__BUCKET', 'docere-records')
    monkeypatch.setenv('APP_QUEUE__BROKER_URL', 'redis://localhost:6379/0')
    monkeypatch.setenv('APP_QUEUE__RESULT_BACKEND', 'redis://localhost:6379/1')


@pytest.mark.critical
def test_create_admin_command_creates_admin_user(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Проверить создание администратора через management CLI.

    Args:
        monkeypatch: Инструмент подмены переменных окружения в тесте.
        tmp_path: Временный каталог pytest.
    """
    sqlite_path = tmp_path / 'management-cli.sqlite3'
    plain_password = 'VeryStrongPass123'  # noqa: S105
    _set_required_env(monkeypatch, sqlite_path)
    clear_settings_cache()
    clear_db_session_cache()
    Base.metadata.create_all(bind=get_engine())

    exit_code = main(
        [
            'create-admin',
            '--email',
            'admin@example.com',
            '--password',
            plain_password,
            '--fio',
            'Главный администратор',
            '--phone',
            '+79990000001',
        ]
    )

    assert exit_code == 0

    with get_session_factory()() as session:
        user = session.scalar(select(UserRow).where(UserRow.email == 'admin@example.com'))

    clear_db_session_cache()
    clear_settings_cache()

    assert user is not None
    assert user.role.value == 'admin'
    assert user.status.value == 'active'
    assert user.password_hash != plain_password


@pytest.mark.critical
def test_create_admin_command_returns_error_for_duplicate_email(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Проверить ошибку CLI при попытке повторно создать администратора.

    Args:
        monkeypatch: Инструмент подмены переменных окружения в тесте.
        tmp_path: Временный каталог pytest.
    """
    sqlite_path = tmp_path / 'management-cli-duplicate.sqlite3'
    _set_required_env(monkeypatch, sqlite_path)
    clear_settings_cache()
    clear_db_session_cache()
    Base.metadata.create_all(bind=get_engine())

    first_exit_code = main(['create-admin', '--email', 'admin@example.com', '--password', 'VeryStrongPass123'])
    second_exit_code = main(['create-admin', '--email', 'admin@example.com', '--password', 'VeryStrongPass123'])

    clear_db_session_cache()
    clear_settings_cache()

    assert first_exit_code == 0
    assert second_exit_code == 1


@pytest.mark.critical
def test_seed_demo_command_is_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Проверить, что команда seed-demo наполняет базу и идемпотентна.

    Args:
        monkeypatch: Инструмент подмены переменных окружения в тесте.
        tmp_path: Временный каталог pytest.
    """
    sqlite_path = tmp_path / 'management-cli-seed.sqlite3'
    _set_required_env(monkeypatch, sqlite_path)
    clear_settings_cache()
    clear_db_session_cache()
    Base.metadata.create_all(bind=get_engine())
    archive_path = tmp_path / 'seed-demo.zip'

    first_exit_code = main(['seed-demo', '--archive-output', str(archive_path)])
    second_exit_code = main(['seed-demo'])

    with get_session_factory()() as session:
        user_count = session.scalar(select(func.count()).select_from(UserRow))
        record_count = session.scalar(select(func.count()).select_from(MedicalRecordRow))

    clear_db_session_cache()
    clear_settings_cache()

    assert first_exit_code == 0
    assert second_exit_code == 0
    assert archive_path.is_file()
    # Повторный запуск не дублирует данные.
    assert user_count == 6
    assert record_count == 4


@pytest.mark.critical
def test_migrate_command_runs_alembic_upgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    """Проверить запуск миграций через management CLI.

    Args:
        monkeypatch: Инструмент подмены объектов в тесте.
    """
    called: dict[str, Any] = {}

    def fake_upgrade(config: Any, revision: str) -> None:
        """Запомнить параметры вызова Alembic upgrade.

        Args:
            config: Экземпляр конфигурации Alembic.
            revision: Целевая ревизия миграции.
        """
        called['config_path'] = config.config_file_name
        called['revision'] = revision

    monkeypatch.setattr('app.presentation.cli.command.upgrade', fake_upgrade)

    exit_code = main(['migrate'])

    assert exit_code == 0
    assert called['config_path'] == 'alembic.ini'
    assert called['revision'] == 'head'


@pytest.mark.critical
def test_build_demo_archive_command_creates_zip(tmp_path: Path) -> None:
    """Проверить создание синтетического архива management-командой.

    Args:
        tmp_path: Временный каталог pytest.
    """
    output_path = tmp_path / 'demo.zip'

    exit_code = main(['build-demo-archive', '--output', str(output_path)])

    assert exit_code == 0
    with ZipFile(output_path) as archive:
        paths = archive.namelist()
    assert any(path.endswith('.dcm') for path in paths)
    assert '../unsafe-demo.txt' in paths

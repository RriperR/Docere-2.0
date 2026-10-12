"""Проверки изоляции pilot, отрицательных secrets и сохранения предыдущих assets."""

import importlib.util
import logging
import os
import subprocess  # noqa: S404 — execute the checked-in publisher only
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pilot = load_module(ROOT / 'scripts/pilot.py')
runtime = load_module(ROOT / 'deploy/pilot/runtime.py')


@pytest.fixture
def config(tmp_path):
    values = dict(
        line.split('=', 1)
        for line in (ROOT / 'deploy/pilot/env.example').read_text().splitlines()
        if line and not line.startswith('#')
    )
    for name in (*pilot.SECRET_NAMES, 'TLS_CERT', 'TLS_KEY', 'AI_TOKEN'):
        path = tmp_path / name
        path.write_text('a' * 64)
        values[f'PILOT_{name}_FILE'] = str(path)
    return values


def write_env(tmp_path, values):
    path = tmp_path / 'pilot.env'
    path.write_text(''.join(f'{key}={value}\n' for key, value in values.items()))
    return path


def test_config_sets_exact_authority(tmp_path, config):
    assert pilot.read_config(write_env(tmp_path, config))['PILOT_AUTHORITY'] == 'localhost:18443'


@pytest.mark.parametrize(
    ('key', 'value'),
    [
        ('PILOT_PROJECT', 'docere'),
        ('PILOT_PORT', '8012'),
        ('PILOT_PORT', '443'),
        ('PILOT_HOST', 'localhost;return 200'),
        ('PILOT_ORIGIN', 'http://localhost:18443'),
        ('PILOT_ORIGIN', 'https://localhost:18443/path'),
        ('PILOT_API_IMAGE', 'docere-api:latest'),
        ('PILOT_AI_ENABLED', 'yes'),
    ],
)
def test_config_rejects_unsafe_values(tmp_path, config, key, value):
    config[key] = value
    with pytest.raises(ValueError):
        pilot.read_config(write_env(tmp_path, config))


@pytest.mark.parametrize('password', ['docere', 'minioadmin', 'dev-secret-key', 'DemoPass123', 'short', ' ' * 64])
def test_no_demo_credentials(tmp_path, config, password):
    Path(config['PILOT_POSTGRES_PASSWORD_FILE']).write_text(password)
    with pytest.raises(ValueError, match='Invalid secret'):
        pilot.read_config(write_env(tmp_path, config))


def test_ai_enabled_requires_configuration(tmp_path, config):
    config['PILOT_AI_ENABLED'] = 'true'
    with pytest.raises(ValueError, match='requires model'):
        pilot.read_config(write_env(tmp_path, config))


def test_short_opaque_ai_token_is_accepted(tmp_path, config, monkeypatch):
    config.update(PILOT_AI_ENABLED='true', PILOT_AI_BASE_URL='https://ai.example.com', PILOT_AI_MODEL='test-model')
    Path(config['PILOT_AI_TOKEN_FILE']).write_text('short-provider-key')
    assert pilot.read_config(write_env(tmp_path, config))['PILOT_AI_ENABLED'] == 'true'
    (tmp_path / 'ai_token').write_text('short-provider-key')
    monkeypatch.setattr(runtime, 'Path', lambda _: tmp_path)
    assert runtime.read_secret('ai_token') == 'short-provider-key'


@pytest.mark.parametrize('token', ['', '   ', 'provider\nkey', 'provider\rkey'])
def test_ai_token_must_be_nonempty_without_line_breaks(tmp_path, config, monkeypatch, token):
    config.update(PILOT_AI_ENABLED='true', PILOT_AI_BASE_URL='https://ai.example.com', PILOT_AI_MODEL='test-model')
    Path(config['PILOT_AI_TOKEN_FILE']).write_text(token)
    with pytest.raises(ValueError, match='requires a secret token'):
        pilot.read_config(write_env(tmp_path, config))
    (tmp_path / 'ai_token').write_text(token)
    monkeypatch.setattr(runtime, 'Path', lambda _: tmp_path)
    with pytest.raises(ValueError, match='Invalid pilot secret'):
        runtime.read_secret('ai_token')


def test_runtime_guard_before_app_import(monkeypatch):
    monkeypatch.setattr(runtime, 'read_secret', lambda name: (_ for _ in ()).throw(ValueError('weak')))
    monkeypatch.setattr(runtime.sys, 'argv', ['runtime.py', 'worker'])
    assert runtime.main() == 1


def test_uvicorn_configuration_cannot_reenable_query_access_logs(monkeypatch):
    from uvicorn import Config
    from uvicorn.config import LOGGING_CONFIG

    monkeypatch.setitem(
        LOGGING_CONFIG['loggers'], 'uvicorn.access', deepcopy(LOGGING_CONFIG['loggers']['uvicorn.access'])
    )
    monkeypatch.setattr(runtime, 'configure', lambda: None)
    monkeypatch.setattr(sys, 'argv', ['runtime.py', 'serve'])
    monkeypatch.setitem(sys.modules, 'app.presentation.cli', SimpleNamespace(main=lambda args: 0))
    assert runtime.main() == 0
    Config('unused:app')
    assert logging.getLogger('uvicorn.access').handlers == []
    assert logging.getLogger('uvicorn.access').propagate is False


def test_compose_never_uses_default_project_or_inherited_pilot_env(tmp_path, config, monkeypatch):
    monkeypatch.setenv('PILOT_PROJECT', 'existing-user-stack')
    calls = []
    monkeypatch.setattr(pilot.subprocess, 'run', lambda command, **kwargs: calls.append((command, kwargs)))
    env_file = write_env(tmp_path, config)
    values = pilot.read_config(env_file)
    pilot.compose(env_file, values, 'config', '--quiet')
    command, kwargs = calls[0]
    assert command[command.index('--project-name') + 1] == 'docere-pilot-local'
    assert command[command.index('--file') + 1] == str(ROOT / 'compose.pilot.yaml')
    assert kwargs['env']['PILOT_PROJECT'] == 'docere-pilot-local'


def test_failed_migration_does_not_start_writers(tmp_path, config, monkeypatch):
    calls = []

    def run_compose(path, values, *args, **kwargs):
        calls.append(args)
        if args == ('run', '--rm', '--no-deps', 'migrate'):
            raise subprocess.CalledProcessError(1, 'migrate')

    monkeypatch.setattr(pilot, 'compose', run_compose)
    monkeypatch.setattr(sys, 'argv', ['pilot.py', 'up', '--env', str(write_env(tmp_path, config))])
    with pytest.raises(subprocess.CalledProcessError):
        pilot.main()
    assert calls[-2][0] == 'stop'
    assert {'gateway', 'api', 'celery-worker', 'import-dispatcher', 'frontend'} <= set(calls[-2])
    assert calls[-1] == ('run', '--rm', '--no-deps', 'migrate')


def test_assets_survive_update_and_reject_name_collision(tmp_path):
    source, target = tmp_path / 'source', tmp_path / 'target'
    source.mkdir()
    target.mkdir()
    old_asset = source / 'old-hash.js'
    old_asset.write_text('old lazy chunk')
    environment = dict(os.environ, ASSETS_SOURCE=str(source), ASSETS_DEST=str(target))
    command = ['/bin/sh', str(ROOT / 'deploy/pilot/publish-assets.sh')]
    subprocess.run(command, env=environment, check=True)  # noqa: S603
    old_asset.unlink()
    (source / 'new-hash.js').write_text('new lazy chunk')
    subprocess.run(command, env=environment, check=True)  # noqa: S603
    assert (target / 'old-hash.js').read_text() == 'old lazy chunk'
    assert (target / 'new-hash.js').read_text() == 'new lazy chunk'
    (source / 'old-hash.js').write_text('unexpected collision')
    result = subprocess.run(command, env=environment, capture_output=True)  # noqa: S603
    assert result.returncode != 0
    assert (target / 'old-hash.js').read_text() == 'old lazy chunk'

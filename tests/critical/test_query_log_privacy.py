"""Регрессии логов gateway и HTTP runner: поисковый q не попадает в access logs."""

from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.critical


def test_main_compose_gateway_uses_query_free_access_log():
    config_path = ROOT / 'deploy/nginx/docere.conf'
    assert './deploy/nginx/docere.conf:/etc/nginx/nginx.conf:ro' in (ROOT / 'docker-compose.yml').read_text()
    config = config_path.read_text()
    log_format = config.split('log_format upstreamlog', 1)[1].split(';', 1)[0]
    assert '$request_method $uri $server_protocol' in log_format
    assert '$request"' not in log_format
    assert '$request_uri' not in log_format
    assert '$args' not in log_format
    assert '$query_string' not in log_format
    assert 'error_log /dev/null crit;' in config


def test_http_runner_disables_uvicorn_query_access_log(record_client, monkeypatch):
    from app.presentation.webserver import server_runner

    seen = []

    class FakeServer:
        def __init__(self, config, **kwargs):
            seen.append(config)

        def run(self):
            pass

    monkeypatch.setattr(
        server_runner, 'app', SimpleNamespace(state=SimpleNamespace(graceful_shutdown_controller=object()))
    )
    monkeypatch.setattr(server_runner, 'GracefulShutdownServer', FakeServer)
    monkeypatch.setattr(
        server_runner, 'get_settings', lambda: SimpleNamespace(graceful_shutdown_reject_window_seconds=1)
    )
    server_runner.run_http_server()
    assert len(seen) == 1
    assert seen[0].access_log is False


def test_application_http_log_omits_search_query(record_client, capsys):
    response = record_client.get('/api/patients/page', params={'q': 'SYNTHETIC_B1_PRIVATE_SEARCH'})
    assert response.status_code == 401
    logs = capsys.readouterr().out
    assert '/api/patients/page' in logs
    assert 'SYNTHETIC_B1_PRIVATE_SEARCH' not in logs

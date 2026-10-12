"""Проверить HTTPS, ACL gateway, assets, вход и синтетический import без seed/reset."""

from __future__ import annotations

import argparse
import re
import secrets
import ssl
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

import httpx
from pilot import compose, read_config

from app.infrastructure.adapters.import_jobs.demo_archive import build_demo_archive


def smoke(env_file: Path) -> None:
    """Проверить пациента и CLI-admin, затем skip всех синтетических кандидатов.

    Args:
        env_file: Проверенная конфигурация изолированного локального стенда.

    Raises:
        RuntimeError: Если проверка поведения завершилась неуспешно.
        TimeoutError: Если import не подготовил review за 90 секунд.
    """
    values = read_config(env_file)
    tls = ssl.create_default_context(cafile=values['PILOT_TLS_CERT_FILE'])
    with httpx.Client(base_url=values['PILOT_ORIGIN'], verify=tls, timeout=20, trust_env=False) as client:
        client.get('/api/health').raise_for_status()
        ui = client.get('/')
        ui.raise_for_status()
        match = re.search(r'(?:src|href)="(/assets/[^" ]+)"', ui.text)
        if '<div id="root">' not in ui.text or not match:
            raise RuntimeError('Frontend root/assets unavailable')
        asset = client.get(match.group(1))
        asset.raise_for_status()
        if 'immutable' not in asset.headers.get('cache-control', ''):
            raise RuntimeError('Retained assets lack immutable caching')
        for path, headers, status in (
            ('/api/health', {'Host': 'untrusted.example'}, 421),
            ('/api/health', {'Origin': 'https://untrusted.example'}, 403),
            ('/api/auth/me', {}, 401),
            ('/docs', {}, 404),
        ):
            if client.get(path, headers=headers).status_code != status:
                raise RuntimeError('Gateway/auth negative smoke failed')
        email, password = f'pilot-{uuid4().hex}@example.com', secrets.token_urlsafe(32)
        registration = client.post(
            '/api/auth/register',
            json={
                'fio': 'Синтетический пользователь пилота',
                'email': email,
                'phone': '+70000000000',
                'password': password,
            },
        )
        registration.raise_for_status()
        login = client.post('/api/auth/login', json={'email': email, 'password': password})
        login.raise_for_status()
        headers = {'Authorization': f'Bearer {login.json()["access_token"]}'}
        client.get('/api/auth/me', headers=headers).raise_for_status()
        denied = client.post(
            '/api/archives/imports',
            headers=headers,
            files={'file': ('pilot-synthetic.zip', build_demo_archive(), 'application/zip')},
        )
        if denied.status_code != 403:
            raise RuntimeError('Patient must not import archives')
        admin_email, admin_password = f'pilot-admin-{uuid4().hex}@example.com', secrets.token_urlsafe(32)
        compose(
            env_file.resolve(),
            values,
            'run',
            '--rm',
            '--no-deps',
            '-T',
            'api',
            'admin',
            admin_email,
            stdin=admin_password + '\n',
        )
        login = client.post('/api/auth/login', json={'email': admin_email, 'password': admin_password})
        login.raise_for_status()
        headers = {'Authorization': f'Bearer {login.json()["access_token"]}'}
        upload = client.post(
            '/api/archives/imports',
            headers=headers,
            files={'file': ('pilot-synthetic.zip', build_demo_archive(), 'application/zip')},
        )
        upload.raise_for_status()
        job_id = upload.json()['id']
        deadline = monotonic() + 90
        while monotonic() < deadline:
            response = client.get(f'/api/archives/imports/{job_id}', headers=headers)
            response.raise_for_status()
            job = response.json()
            if job['status'] == 'failed':
                raise RuntimeError('Synthetic import failed; inspect private diagnostics locally')
            if job['status'] == 'needs_review':
                break
            sleep(1)
        else:
            raise TimeoutError('Synthetic import did not reach review')
        decisions = [
            {'candidate_id': item['candidate_id'], 'action': 'skip', 'record_groups': []}
            for item in job['report_json']['patients']
        ]
        resolved = client.post(
            f'/api/archives/imports/{job_id}/resolve', headers=headers, json={'decisions': decisions}
        )
        resolved.raise_for_status()
        if resolved.json()['status'] not in {'completed', 'completed_with_warnings'}:
            raise RuntimeError('Synthetic import did not complete')
    print('Pilot smoke passed: TLS, host/origin rejection, UI/assets, auth and import review/skip.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env', type=Path, required=True)
    smoke(parser.parse_args().env)

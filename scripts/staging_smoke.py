"""Проверка UI, auth и безопасного import workflow на demo staging."""

from __future__ import annotations

import os
from time import monotonic, sleep

import httpx

from app.infrastructure.adapters.import_jobs.demo_archive import build_demo_archive


def main() -> None:
    """Выполнить staging smoke test до финального статуса import job.

    Raises:
        RuntimeError: Если UI или import workflow не готовы.
    """
    base_url = os.environ['STAGING_BASE_URL'].rstrip('/')
    email = os.environ.get('STAGING_SMOKE_EMAIL', 'dr.sokolov@docere.demo')
    password = os.environ.get('STAGING_SMOKE_PASSWORD', 'DemoPass123')
    with httpx.Client(base_url=base_url, timeout=20) as client:
        health = client.get('/api/health')
        health.raise_for_status()
        frontend = client.get('/')
        frontend.raise_for_status()
        if '<div id="root">' not in frontend.text:
            raise RuntimeError('Frontend root element is missing')

        login = client.post('/api/auth/login', json={'email': email, 'password': password})
        login.raise_for_status()
        headers = {'Authorization': f'Bearer {login.json()["access_token"]}'}
        upload = client.post(
            '/api/archives/imports',
            headers=headers,
            files={'file': ('docere-demo-archive.zip', build_demo_archive(), 'application/zip')},
        )
        upload.raise_for_status()
        job_id = upload.json()['id']
        job = _wait_for_review(client=client, job_id=job_id, headers=headers)
        decisions = [
            {'candidate_id': patient['candidate_id'], 'action': 'skip', 'record_groups': []}
            for patient in job['report_json']['patients']
        ]
        resolved = client.post(
            f'/api/archives/imports/{job_id}/resolve',
            headers=headers,
            json={'decisions': decisions},
        )
        resolved.raise_for_status()
        if resolved.json()['status'] not in {'completed', 'completed_with_warnings'}:
            raise RuntimeError('Import job did not reach a completed status')


def _wait_for_review(*, client: httpx.Client, job_id: str, headers: dict[str, str]) -> dict[str, object]:
    """Дождаться готовности import review.

    Returns:
        Ответ API для задания в статусе ``needs_review``.

    Raises:
        RuntimeError: Если обработка архива завершилась ошибкой.
        TimeoutError: Если worker не подготовил review за 90 секунд.
    """
    deadline = monotonic() + 90
    while monotonic() < deadline:
        response = client.get(f'/api/archives/imports/{job_id}', headers=headers)
        response.raise_for_status()
        job = response.json()
        if job['status'] == 'needs_review':
            return job
        if job['status'] == 'failed':
            raise RuntimeError(f'Import job failed: {job["report_json"]}')
        sleep(2)
    raise TimeoutError('Import job did not reach needs_review in 90 seconds')


if __name__ == '__main__':
    main()

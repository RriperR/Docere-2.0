"""Воспроизводимый небольшой нагрузочный эксперимент для demo API."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import subprocess  # noqa: S404
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, UTC
from pathlib import Path
from time import monotonic, perf_counter, sleep
from typing import Any

import httpx


@dataclass(frozen=True)
class RateResult:
    """Результат одной серии с фиксированной частотой запросов."""

    target_rps: int
    duration_seconds: int
    requests: int
    achieved_rps: float
    errors: int
    error_percent: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float


def _percentile(values: list[float], percentile: float) -> float:
    """Рассчитать percentile с линейной интерполяцией.

    Returns:
        Значение percentile.
    """
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _request(client: httpx.Client, path: str) -> tuple[float, bool]:
    started = perf_counter()
    try:
        response = client.get(path)
        response.raise_for_status()
        success = True
    except httpx.HTTPError:
        success = False
    return (perf_counter() - started) * 1000, success


def _run_rate(*, client: httpx.Client, path: str, rate: int, duration: int) -> RateResult:
    total = rate * duration
    interval = 1 / rate
    futures: list[Future[tuple[float, bool]]] = []
    started = monotonic()
    with ThreadPoolExecutor(max_workers=max(8, rate * 2)) as pool:
        for index in range(total):
            due = started + index * interval
            remaining = due - monotonic()
            if remaining > 0:
                sleep(remaining)
            futures.append(pool.submit(_request, client, path))
    elapsed = monotonic() - started
    samples = [future.result() for future in futures]
    latencies = [latency for latency, _ in samples]
    errors = sum(not success for _, success in samples)
    return RateResult(
        target_rps=rate,
        duration_seconds=duration,
        requests=total,
        achieved_rps=round(total / elapsed, 2),
        errors=errors,
        error_percent=round(errors / total * 100, 2),
        p50_ms=round(_percentile(latencies, 0.50), 2),
        p95_ms=round(_percentile(latencies, 0.95), 2),
        p99_ms=round(_percentile(latencies, 0.99), 2),
        max_ms=round(max(latencies), 2),
    )


def _git_revision() -> str:
    return subprocess.run(  # noqa: S603
        ['/usr/bin/git', 'rev-parse', 'HEAD'],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _target_path(client: httpx.Client) -> str:
    patients = client.get('/api/patients')
    patients.raise_for_status()
    payload: list[dict[str, Any]] = patients.json()
    if not payload:
        raise RuntimeError('В demo-стенде нет пациентов. Выполните make demo-reset.')
    return f'/api/patients/{payload[0]["id"]}/records'


def main() -> None:
    """Запустить серии и сохранить машинно-читаемый отчёт."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://localhost:8000')
    parser.add_argument('--email', default='dr.sokolov@docere.demo')
    parser.add_argument('--password', default='DemoPass123')
    parser.add_argument('--rates', nargs='+', type=int, default=[5, 10, 20])
    parser.add_argument('--duration', type=int, default=10)
    parser.add_argument('--output', type=Path, default=Path('artifacts/benchmark-results.json'))
    args = parser.parse_args()

    with httpx.Client(base_url=args.base_url.rstrip('/'), timeout=20) as anonymous:
        login = anonymous.post('/api/auth/login', json={'email': args.email, 'password': args.password})
        login.raise_for_status()
        token = login.json()['access_token']

    with httpx.Client(
        base_url=args.base_url.rstrip('/'),
        headers={'Authorization': f'Bearer {token}'},
        timeout=20,
    ) as client:
        path = _target_path(client)
        results = [_run_rate(client=client, path=path, rate=rate, duration=args.duration) for rate in args.rates]

    report = {
        'measured_at': datetime.now(UTC).isoformat(),
        'git_revision': _git_revision(),
        'host': {
            'platform': platform.platform(),
            'machine': platform.machine(),
            'processor_count': os.cpu_count(),
        },
        'base_url': args.base_url,
        'endpoint': path,
        'results': [asdict(result) for result in results],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

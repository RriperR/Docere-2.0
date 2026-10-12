"""Управлять только изолированным локальным Compose-проектом Docere pilot."""

from __future__ import annotations

import argparse
import getpass
import os
import re
import secrets
import shutil
import subprocess  # noqa: S404 — explicit argument arrays only, no shell
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SECRET_NAMES = ('AUTH_KEY', 'POSTGRES_PASSWORD', 'REDIS_PASSWORD', 'STORAGE_ACCESS_KEY', 'STORAGE_SECRET_KEY')
FORBIDDEN = {'docere', 'minioadmin', 'dev-secret-key', 'change-me-in-production', 'DemoPass123'}


def read_config(path: Path) -> dict[str, str]:
    """Проверить env, обязательные secrets и единственный локальный HTTPS origin.

    Args:
        path: Env-файл вне build context.

    Returns:
        Проверенные переменные Compose без содержимого secrets.

    Raises:
        ValueError: Если конфигурация небезопасна или неполна.
    """
    values = {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or not re.fullmatch(r'PILOT_[A-Z_]+', key) or key in values:
            raise ValueError('Invalid or repeated pilot env key')
        values[key] = value
    if not re.fullmatch(r'docere-pilot-[a-z0-9][a-z0-9-]*', values.get('PILOT_PROJECT', '')):
        raise ValueError('Project must start with docere-pilot-')
    port = int(values['PILOT_PORT'])
    if not 1024 <= port <= 65535 or port == 8012:
        raise ValueError('Use an isolated unprivileged port other than 8012')
    host = values['PILOT_HOST']
    if not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*', host):
        raise ValueError('Invalid allowed host')
    origin = urlsplit(values['PILOT_ORIGIN'])
    if origin.scheme != 'https' or origin.netloc != f'{host}:{port}' or origin.path or origin.query or origin.fragment:
        raise ValueError('Origin must be exactly https://HOST:PORT')
    values['PILOT_AUTHORITY'] = origin.netloc
    for name in SECRET_NAMES:
        secret_path = Path(values[f'PILOT_{name}_FILE']).resolve()
        value = secret_path.read_text().strip()
        if len(value) < 32 or value in FORBIDDEN or any(char.isspace() for char in value):
            raise ValueError(f'Invalid secret file: {name}')
        if ROOT in secret_path.parents:
            raise ValueError('Secrets must be outside the checkout/build context')
    for name in ('TLS_CERT', 'TLS_KEY', 'AI_TOKEN'):
        secret_path = Path(values[f'PILOT_{name}_FILE']).resolve()
        if not secret_path.is_file() or ROOT in secret_path.parents:
            raise ValueError(f'Missing or unsafe file: {name}')
    if values.get('PILOT_AI_ENABLED') not in {'true', 'false'}:
        raise ValueError('Explicit AI toggle required')
    if values['PILOT_AI_ENABLED'] == 'true':
        if not values.get('PILOT_AI_BASE_URL') or not values.get('PILOT_AI_MODEL'):
            raise ValueError('Enabled AI requires model and URL')
        token = Path(values['PILOT_AI_TOKEN_FILE']).read_text()
        if not token.strip() or '\r' in token or '\n' in token:
            raise ValueError('Enabled AI requires a secret token')
    for name in ('API', 'FRONTEND'):
        image = values[f'PILOT_{name}_IMAGE']
        if not image or ':' not in image or image.endswith(':latest'):
            raise ValueError('Use explicit release image tags or digests')
    return values


def compose(path: Path, values: dict[str, str], *args: str, stdin: str | None = None) -> None:
    """Выполнить Compose с обязательными file/project/env аргументами.

    Args:
        path: Проверенный env-файл.
        values: Проверенные настройки.
        args: Аргументы разрешённой операции Compose.
        stdin: Необязательный secret для stdin bootstrap.

    """
    environment = {key: value for key, value in os.environ.items() if not key.startswith('PILOT_')}
    environment.update(values)
    subprocess.run(  # noqa: S603
        [
            shutil.which('docker') or '/usr/local/bin/docker',
            'compose',
            '--project-name',
            values['PILOT_PROJECT'],
            '--env-file',
            str(path),
            '--file',
            str(ROOT / 'compose.pilot.yaml'),
            *args,
        ],
        cwd=ROOT,
        env=environment,
        input=stdin,
        text=True,
        check=True,
    )


def init_local(directory: Path, port: int, project: str) -> Path:
    """Создать новые локальные secrets и self-signed TLS, не перезаписывая файлы.

    Args:
        directory: Новый закрытый каталог вне checkout.
        port: Изолированный порт gateway.
        project: Новое имя Compose-проекта.

    Returns:
        Путь нового env-файла.

    Raises:
        ValueError: Если каталог находится внутри checkout.
    """
    directory = directory.resolve()
    if directory == ROOT or ROOT in directory.parents:
        raise ValueError('Local secrets directory must be outside the checkout')
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    values = dict(
        line.split('=', 1)
        for line in (ROOT / 'deploy/pilot/env.example').read_text().splitlines()
        if line and not line.startswith('#')
    )
    values.update(PILOT_PROJECT=project, PILOT_PORT=str(port), PILOT_ORIGIN=f'https://localhost:{port}')
    for name in SECRET_NAMES:
        secret_path = directory / name.lower()
        secret_path.write_text(secrets.token_hex(32))
        secret_path.chmod(0o600)
        values[f'PILOT_{name}_FILE'] = str(secret_path)
    token = directory / 'ai_token'
    token.touch(mode=0o600)
    values['PILOT_AI_TOKEN_FILE'] = str(token)
    cert, key = directory / 'tls.crt', directory / 'tls.key'
    subprocess.run(  # noqa: S603
        [
            shutil.which('openssl') or '/usr/bin/openssl',
            'req',
            '-x509',
            '-newkey',
            'rsa:3072',
            '-nodes',
            '-days',
            '7',
            '-subj',
            '/CN=localhost',
            '-addext',
            'subjectAltName=DNS:localhost,IP:127.0.0.1',
            '-keyout',
            str(key),
            '-out',
            str(cert),
        ],
        check=True,
        capture_output=True,
    )
    key.chmod(0o600)
    values.update(PILOT_TLS_CERT_FILE=str(cert), PILOT_TLS_KEY_FILE=str(key))
    path = directory / 'pilot.env'
    path.write_text(''.join(f'{name}={value}\n' for name, value in values.items()))
    path.chmod(0o600)
    read_config(path)
    return path


def main() -> None:
    """Выполнить локальную установку, обновление, диагностику или bootstrap."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('init-local', 'config', 'up', 'rollback', 'status', 'stop', 'logs', 'admin'))
    parser.add_argument('--env', type=Path)
    parser.add_argument('--directory', type=Path)
    parser.add_argument('--port', type=int, default=18443)
    parser.add_argument('--project', default='docere-pilot-local')
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--schema-compatible', action='store_true')
    parser.add_argument('--email')
    parser.add_argument('--service', choices=('gateway', 'api', 'celery-worker', 'import-dispatcher'))
    args = parser.parse_args()
    if args.action == 'init-local':
        if args.directory is None:
            parser.error('--directory is required')
        print(init_local(args.directory, args.port, args.project))
        return
    if args.env is None:
        parser.error('--env is required')
    path = args.env.resolve()
    values = read_config(path)
    if args.action in {'up', 'rollback'}:
        if args.action == 'rollback' and not args.schema_compatible:
            parser.error('rollback requires --schema-compatible after reviewing the migration/release notes')
        compose(path, values, 'config', '--quiet')
        if args.build:
            compose(path, values, 'build', 'api', 'frontend')
        compose(path, values, 'up', '-d', '--wait', '--wait-timeout', '120', 'postgres', 'redis', 'minio')
        compose(path, values, 'run', '--rm', '--no-deps', 'createbuckets')
        compose(path, values, 'run', '--rm', '--no-deps', 'publish-assets')
        compose(path, values, 'stop', 'gateway', 'api', 'celery-worker', 'import-dispatcher', 'frontend')
        # Only this one-shot process migrates; failure keeps writers/ingress stopped.
        if args.action == 'up':
            compose(path, values, 'run', '--rm', '--no-deps', 'migrate')
        compose(
            path,
            values,
            'up',
            '-d',
            '--force-recreate',
            '--wait',
            '--wait-timeout',
            '180',
            'api',
            'celery-worker',
            'import-dispatcher',
            'frontend',
            'gateway',
        )
    elif args.action == 'config':
        compose(path, values, 'config', '--quiet')
        print('Pilot config valid; no public deployment performed.')
    elif args.action == 'status':
        compose(path, values, 'ps', '--all')
    elif args.action == 'stop':
        compose(path, values, 'stop')
    elif args.action == 'logs':
        if args.service is None:
            parser.error('--service is required; review locally before sharing logs')
        compose(path, values, 'logs', '--tail', '80', args.service)
    elif args.action == 'admin':
        if not args.email:
            parser.error('--email is required')
        password = getpass.getpass('New pilot admin password (at least 16 characters): ')
        compose(path, values, 'run', '--rm', '--no-deps', '-T', 'api', 'admin', args.email, stdin=password + '\n')


if __name__ == '__main__':
    main()

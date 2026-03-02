import os


def _set_required_env_defaults() -> None:
    os.environ.setdefault('APP_DATABASE__URL', 'postgresql+psycopg://docere:docere@localhost:5432/docere')
    os.environ.setdefault('APP_AUTH__SECRET_KEY', 'test-secret-key-32-bytes-minimum-0001')
    os.environ.setdefault('APP_STORAGE__ENDPOINT', 'http://localhost:9000')
    os.environ.setdefault('APP_STORAGE__BUCKET', 'docere-records')
    os.environ.setdefault('APP_QUEUE__BROKER_URL', 'redis://localhost:6379/0')


_set_required_env_defaults()

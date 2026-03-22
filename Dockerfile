# syntax=docker/dockerfile:1.7

FROM python:3.13-slim@sha256:739e7213785e88c0f702dcdc12c0973afcbd606dbf021a589cab77d6b00b579d AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

FROM python-base AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=from=ghcr.io/astral-sh/uv:0.10.9@sha256:10902f58a1606787602f303954cea099626a4adb02acbac4c69920fe9d278f82,source=/uv,target=/bin/uv \
    uv sync --frozen --no-install-project --no-group lint --no-group test --no-group benchmark

COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
COPY src ./src

FROM python-base AS runtime

ENV PATH=/app/.venv/bin:$PATH

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --create-home --home-dir /home/app --shell /usr/sbin/nologin --no-log-init app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/alembic.ini ./alembic.ini
COPY --from=builder --chown=app:app /app/migrations ./migrations
COPY --from=builder --chown=app:app /app/src ./src

USER app

EXPOSE 8000

CMD ["uvicorn", "app.presentation.main:app", "--host", "0.0.0.0", "--port", "8000"]

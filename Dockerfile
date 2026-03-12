FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    UV_LINK_MODE=copy

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --all-groups

COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
COPY src ./src
COPY tests ./tests
COPY .env.example ./.env.example

CMD ["uv", "run", "uvicorn", "app.presentation.main:app", "--host", "0.0.0.0", "--port", "8000"]

.PHONY: install install-dev install-lint install-test install-all \
	lint lint-fix format format-check type-check test test-critical \
	test-with-coverage frontend-check project-check migrate-up migrate-down docker-migrate-up \
	dev-backend dev-frontend dev demo-up demo-reset demo-check demo-logs demo-down benchmark

PYTEST_TMPDIR ?= /tmp

install:
	uv sync

install-dev:
	uv sync --group dev

install-lint:
	uv sync --group lint

install-test:
	uv sync --group test

install-all:
	uv sync --all-groups

lint:
	uv run ruff check .

lint-fix:
	uv run ruff check . --fix

format:
	uv run ruff format .

format-check:
	uv run ruff format . --check

type-check:
	uv run mypy --config-file=./mypy.ini src

test:
	TMPDIR=$(PYTEST_TMPDIR) uv run pytest -p no:cacheprovider $(ARGS)

test-critical:
	TMPDIR=$(PYTEST_TMPDIR) uv run pytest -m critical -q -p no:cacheprovider $(ARGS)

test-with-coverage:
	TMPDIR=$(PYTEST_TMPDIR) uv run pytest --cov=src --cov-report=term-missing $(ARGS)

frontend-check:
	cd frontend && npm run build && npm run lint && npm run test

project-check:
	uv run pre-commit run --all-files
	$(MAKE) lint
	$(MAKE) format-check
	$(MAKE) type-check
	$(MAKE) test

migrate-up:
	uv run alembic upgrade head

migrate-down:
	uv run alembic downgrade -1

docker-migrate-up:
	docker compose run --rm --build api migrate

dev-backend:
	PYTHONPATH=src uv run uvicorn app.presentation.main:app --reload

dev-frontend:
	cd frontend && npm run dev

dev:
	docker compose up -d --build
	cd frontend && npm run dev

demo-up:
	./scripts/demo.sh up

demo-reset:
	./scripts/demo.sh reset

demo-check:
	./scripts/demo.sh check

demo-logs:
	./scripts/demo.sh logs

demo-down:
	./scripts/demo.sh down

benchmark:
	uv run python scripts/benchmark_api.py --base-url http://localhost:8000 --rates 5 10 20 --duration 10 --output artifacts/benchmark-results.json

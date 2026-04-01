.PHONY: install install-dev install-lint install-test install-all \
	lint lint-fix format format-check type-check test test-critical \
	test-with-coverage project-check migrate-up migrate-down docker-migrate-up \
	dev-backend dev-frontend dev

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
	uv run pytest -p no:cacheprovider $(ARGS)

test-critical:
	uv run pytest -m critical -q -p no:cacheprovider $(ARGS)

test-with-coverage:
	uv run pytest --cov=src --cov-report=term-missing $(ARGS)

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

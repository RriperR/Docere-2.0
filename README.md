# Docere

Backend quality gate with `uv`, `pre-commit`, `ruff`, `mypy`, and `pytest` for a DDD + Clean Architecture layout.

## Project Structure

```
src/app/
  domain/
  application/
  infrastructure/
  presentation/
```

Dependency direction:

- `domain` does not depend on other layers.
- `application` depends only on `domain`.
- `infrastructure` depends on `application` and `domain`.
- `presentation` depends on `application` and integrates infra via composition/DI.

## Installation

Python: `3.12+`

```bash
uv sync --all-groups
```

## Git Hooks

```bash
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

## Checks

```bash
make lint
make type-check
make test
make project-check
```

## Development Run

```bash
make dev
```

Equivalent command:

```bash
PYTHONPATH=src uv run uvicorn app.presentation.main:app --reload
```
